"""Router node for deciding between portfolio and news nodes."""

from typing import Final, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langgraph.runtime import get_runtime
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.dependencies import LLMFactory
from src.schemas.agent_state import AgentContext, AgentState

logger = logger_for(__name__)


class RouteResponse(BaseModel):
    decision: Literal[Nodes.portfolio.get("name"), Nodes.news.get("name")] = Field(
        validation_alias=AliasChoices("decision", "destination")
    )
    model_config = ConfigDict(extra="ignore")


class RouterNode:
    """Router node for deciding between portfolio and news nodes."""

    _ROUTER_PROMPT_TEMPLATE: Final[
        str
    ] = """
You are a router that must select exactly one destination for the user's query.

Return ONLY a JSON object conforming to RouteResponse (no prose, no extra fields).

Destinations

- "{portfolio_node}": Personalized questions about the user's portfolio/holdings/positions, P&L/returns, allocation/rebalancing, SIP/mutual funds, taxes, risk/exposure, actions to take on their assets, or *any* generic stock/price/fund query that does **not explicitly** ask for news or circulars.
- "{news_node}": **Only** when the query explicitly asks for circulars or news/updates, such as NSE/SEBI/BSE circulars, index change announcements (e.g., NIFTY 50 rebalancing news), company news, earnings/dividend announcements, macro/policy news (RBI/Fed/CPI), or other market headlines.

Decision rules

1. If the query mentions the user's assets explicitly (“my/our portfolio/holdings/positions/SIP/mutual funds”) → "{portfolio_node}".
2. If the query asks for guidance, actions, or analysis that could apply to the user's investments (even if not saying “my”) → "{portfolio_node}".
3. If the query is a generic ticker/stock/fund/index question (e.g., “Current price of RELIANCE”, “Is TCS overvalued?”, “Explain NIFTY 50 PE ratio”) and does **not** explicitly mention news/circulars → "{portfolio_node}".
4. Route to "{news_node}" **only if** the query explicitly references *news-like* terms such as “news”, “headline(s)”, “latest update(s)”, “announcement(s)”, “NSE circular”, “SEBI circular”, “BSE circular”, “circular”, “press release”, “RBI policy news”, etc.
5. If both apply (e.g., “How will today’s RBI news affect my portfolio?”) → "{portfolio_node}".
6. If ambiguous, default to "{portfolio_node}".

Output format
Return: "{portfolio_node}" or "{news_node}".

Examples
 - "What's the latest NSE circular on NIFTY 50 rebalancing?" → "{news_node}"
 - "Last year's balance sheet of RELIANCE?" → "{portfolio_node}"
 - "Latest news on RELIANCE results" → "{news_node}"
 - "News on Adani Green Energy?" → "{news_node}"
 - "Infosys Q2 results?" → "{portfolio_node}"
 - "Should I rebalance my portfolio after the NIFTY 50 changes?" → "{portfolio_node}"
 - "My holdings: TCS 20%, HDFCBANK 15%—is my finance exposure too high?" → "{portfolio_node}"
 - "Current price of RELIANCE" → "{portfolio_node}"
 - "Will the Union Budget impact my SIPs?" → "{portfolio_node}"
    """

    def __init__(self, llm_factory: LLMFactory):
        """Initialize the RouterNode with an injected LLM factory."""
        self._llm_factory = llm_factory

    def _router_prompt_template(self) -> ChatPromptTemplate:
        router_prompt_template = self._ROUTER_PROMPT_TEMPLATE.format(
            portfolio_node=Nodes.portfolio.get("name"), news_node=Nodes.news.get("name")
        )
        chat_template = ChatPromptTemplate.from_messages(
            [
                ("system", router_prompt_template),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        return chat_template

    def __respect_history_and_initialize_context(
        self, agent_state: AgentState, context: AgentContext
    ) -> AgentContext:
        """
        Respect the history of messages and initialize the context.
        """

        history_message_length = (
            len(agent_state.get("messages", [])) - 1
        )  # -1 to exclude the human message
        agent_state["history_message_length"] = history_message_length
        user_id = context.get("user_id", "unknown")
        logger.info(
            "Router node invoked for user_id=%s with history_message_length=%s",
            user_id,
            history_message_length,
        )
        context["history_message_length"] = history_message_length
        return context

    def get_runnable_sequence(self):
        prompt = self._router_prompt_template()

        def router_node_fn(state: AgentState) -> AgentState:
            # 🔹 Access AgentContext via runtime
            runtime = get_runtime(AgentContext)
            context = runtime.context

            # state.messages hold the history of messages, so update the history_message_length
            context = self.__respect_history_and_initialize_context(state, context)

            router_model = context.get("router_model", LLMModel.GPT4oMini)
            llm = self._llm_factory(router_model)
            chain = prompt | llm.with_structured_output(RouteResponse)

            messages = state.get("messages", [])
            rr = chain.invoke({"messages": messages})
            router_msg = AIMessage(content=rr.model_dump_json(), name="router")
            user_request = state.get("user_request", "")
            for message in reversed(messages):
                if isinstance(message, HumanMessage):
                    user_request = message.content
                    break
            return {
                **state,
                "messages": messages + [router_msg],
                "user_request": user_request,
            }

        return RunnableLambda(router_node_fn)

    def _get_router_decision(self, state: AgentState, name: str = "router") -> str:
        ALLOWED = [Nodes.portfolio.get("name"), Nodes.news.get("name")]
        messages = state.get("messages", [])
        for m in reversed(messages):
            if isinstance(m, AIMessage) and getattr(m, "name", None) == name:
                try:
                    if isinstance(m.content, str) and hasattr(RouteResponse, "model_validate_json"):
                        rr = RouteResponse.model_validate_json(m.content)  # pydantic v2
                    elif isinstance(m.content, dict) and hasattr(RouteResponse, "model_validate"):
                        rr = RouteResponse.model_validate(m.content)  # pydantic v2
                    elif isinstance(m.content, str):
                        rr = RouteResponse.parse_raw(m.content)  # pydantic v1
                    else:
                        rr = RouteResponse.parse_obj(m.content)  # pydantic v1
                except Exception as e:
                    logger.error("Router decision failed: %s", str(e), exc_info=True)
                    break
                return rr.decision if rr.decision in ALLOWED else Nodes.unknown.get("name")
        return Nodes.unknown.get("name")

    def router_decision(self, state: AgentState) -> str:
        """
        Make a routing decision based on the current state.

        Args:
            state: AgentState representing the current conversation state

        Returns:
            str: The node to route to ('portfolio_node', 'news_node', or 'unknown_node')
        """
        # 🔹 Access context again when computing the decision (used by conditional edge)
        runtime = get_runtime(AgentContext)
        user_id = runtime.context["user_id"]
        logger.info("Router decision evaluated for user_id=%s", user_id)

        messages = state.get("messages", [])
        ai_message_count = sum(isinstance(item, AIMessage) for item in messages)
        decision = self._get_router_decision(state)

        if ai_message_count > Nodes.router.get("max_ai_messages_allowed"):
            logger.warning(
                "Router max iterations (%d) exceeded for user_id=%s, routing to unknown_node",
                Nodes.router.get("max_ai_messages_allowed"),
                user_id,
            )
            return Nodes.unknown.get("name")

        try:
            valid_nodes = {Nodes.portfolio.get("name"), Nodes.news.get("name")}
            if decision in valid_nodes:
                logger.info("Router decision for user_id=%s: %s", user_id, decision)
                return decision
            logger.warning(
                "Router returned unexpected decision for user_id=%s: %s",
                user_id,
                decision,
            )
            return Nodes.unknown.get("name")
        except Exception as e:
            logger.error(
                "Router decision failed for user_id=%s: %s",
                user_id,
                str(e),
                exc_info=True,
            )
            return Nodes.unknown.get("name")
