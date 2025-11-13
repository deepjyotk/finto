"""Router node for deciding between portfolio and news nodes."""

from typing import Final, List, Literal

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnableSequence
from langchain_openai import ChatOpenAI
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for

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
    - "{portfolio_node}": Personalized questions about the user's portfolio/holdings/positions, P&L/returns, allocation/rebalancing, SIP/mutual funds, taxes, risk/exposure, or actions to take on their assets.
    - "{news_node}": General market information or events not specific to the user's portfolio: NSE/SEBI/BSE circulars, index changes (e.g., NIFTY 50), company/ticker news, earnings/dividends, macro/policy (RBI/Fed/CPI), prices/quotes.

    Decision rules
    1) If the query references “my/our portfolio/holdings/positions” or asks for actions/advice tailored to the user's assets → "{portfolio_node}".
    2) If the query requests market/regulatory/news updates or price/quote lookups without user-specific context → "{news_node}".
    3) If both apply (e.g., “How will today’s RBI hike affect my portfolio?”) → "{portfolio_node}".
    4) If ambiguous, default to "{news_node}".

    Output format
    Return: "{portfolio_node}" or "{news_node}".

    Examples
    - "What's the latest NSE circular on NIFTY 50 rebalancing?" → "{news_node}"
    - "Should I rebalance my portfolio after the NIFTY 50 changes?" → "{portfolio_node}"
    - "My holdings: TCS 20%, HDFCBANK 15%—is my finance exposure too high?" → "{portfolio_node}"
    - "INFY Q2 results highlights?" → "{news_node}"
    - "Current price of RELIANCE" → "{news_node}"
    - "Will the Union Budget impact my SIPs?" → "{portfolio_node}"
    """

    def __init__(self):
        """Initialize the RouterNode."""

    def _router_prompt_template(self) -> ChatPromptTemplate:
        """
        Create the router prompt template.

        Returns:
            ChatPromptTemplate: The complete prompt template for routing
        """
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

    # def get_runnable_sequence(self, model: LLMModel):
    #     """
    #     Create the router runnable chain with structured output.

    #     Args:
    #         model: The LLM model to use

    #     Returns:
    #         The runnable chain for router decision making
    #     """
    #     llm = ChatOpenAI(model=model.value, temperature=0)
    #     parser = PydanticToolsParser(tools=[RouteResponse])
    #     prompt_template = self._router_prompt_template()
    #     runnable_sequence = RunnableSequence(prompt_template |  llm)
    #     return runnable_sequence

    def get_runnable_sequence(self, model: LLMModel) -> RunnableSequence:
        llm = ChatOpenAI(model=model.value, temperature=0)
        prompt = self._router_prompt_template()
        chain = prompt | llm.with_structured_output(RouteResponse)

        # MessageGraph will pass List[BaseMessage]; map to the chain's expected input,
        # then map the structured output to a named AIMessage.
        # AIMessage(content={decision:"portfolio_node"}, name="router")
        return (
            RunnableLambda(lambda msgs: {"messages": msgs})
            | chain
            | RunnableLambda(lambda rr: [AIMessage(content=rr.model_dump_json(), name="router")])
        )

    def _get_router_decision(self, state: List[BaseMessage], name: str = "router") -> str:
        ALLOWED = ["portfolio_node", "news_node"]
        for m in reversed(state):
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
                except Exception:
                    break
                return rr.decision if rr.decision in ALLOWED else "unknown_node"
        return "unknown_node"

    def router_decision(self, state: List[BaseMessage]) -> str:
        """
        Make a routing decision based on the current state.

        Args:
            state: List of messages representing the current conversation state
            model: The LLM model to use for decision making

        Returns:
            str: The node to route to ('portfolio_node', 'news_node', or 'unknown_node')
        """

        # TODO: count the past ai messsage and check if has crossed the limit
        # count_tool_visits = sum(isinstance(item, ToolMessage) for item in state)
        ai_message_count = sum(isinstance(item, AIMessage) for item in state)
        decision = self._get_router_decision(state)

        if ai_message_count > Nodes.router.get("max_ai_messages_allowed"):
            logger.warning(
                "Router max iterations (%d) exceeded, routing to unknown_node",
                Nodes.router.get("max_ai_messages_allowed"),
            )
            return Nodes.unknown.get("name")

        # Use the router runnable chain to make the decision
        try:
            valid_nodes = {Nodes.portfolio.get("name"), Nodes.news.get("name")}
            if decision in valid_nodes:
                logger.info("Router decision: %s", decision)
                return decision
            logger.warning("Router returned unexpected decision: %s", decision)
            return Nodes.unknown.get("name")
        except Exception as e:
            logger.error("Router decision failed: %s", str(e), exc_info=True)
            return Nodes.unknown.get("name")
