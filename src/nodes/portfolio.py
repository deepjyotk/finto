"""Portfolio symbol extraction node."""

from typing import Callable, List, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.runtime import get_runtime
from pydantic import BaseModel

from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.schemas.agent_state import AgentContext, AgentState
from src.tools.get_symbol_name import get_symbol_names

logger = logger_for(__name__)


class SymbolExtractionResult(BaseModel):
    """Pydantic model for validating symbol extraction output."""

    symbol_names: List[str]


class QueryTypeResult(BaseModel):
    """Pydantic model for classifying portfolio query scope."""

    query_type: Literal["specific_stocks_scope", "entire_portfolio_scope"]


class PortfolioNode:
    """Portfolio node responsible for extracting symbol names."""

    def __init__(self, llm_factory: Callable[[LLMModel], ChatOpenAI]):
        """Initialize PortfolioNode with injected LLM factory."""
        self._llm_factory = llm_factory

    @staticmethod
    def _latest_user_message_content(messages: List[BaseMessage]) -> str:
        """Find the most recent human message content."""
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message.content
        return ""

    def get_runnable_sequence(self):
        """Return the runnable sequence for the portfolio node."""

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a classifier for portfolio questions.\n"
                        "Decide whether the user's question is scoped ONLY to specific named stocks, "
                        "or to the entire portfolio (including questions that compare one stock to the rest of the portfolio).\n"
                        "Return ONLY one of the following (no explanations, no extra text):\n"
                        "- specific_stocks_scope\n"
                        "- entire_portfolio_scope"
                    ),
                ),

                # ==== Few-shot examples ====
                ("human", "What's the profit of my portfolio?"),
                ("ai", "entire_portfolio_scope"),

                ("human", "What's the profit of BAJFINANCE?"),
                ("ai", "specific_stocks_scope"),

                ("human", "What's the loss of Reliance and TATA?"),
                ("ai", "specific_stocks_scope"),

                ("human", "Compare prices of TATA with the other stocks?"),
                ("ai", "entire_portfolio_scope"),

                ("human", "Show my sector-wise allocation"),
                ("ai", "entire_portfolio_scope"),

                ("human", "How much have I gained in HDFC Bank since I bought it?"),
                ("ai", "specific_stocks_scope"),

                ("human", "Which are my top 5 holdings by value?"),
                ("ai", "entire_portfolio_scope"),

                ("human", "Between INFY and TCS, which one is performing better in my portfolio?"),
                ("ai", "specific_stocks_scope"),

                # ==== Actual user query ====
                ("human", "{user_query}"),
            ]
        )

        def portfolio_node_fn(state: AgentState) -> AgentState:
            messages = state.get("messages", [])
            user_request = state.get("user_request") or self._latest_user_message_content(messages)
            user_query = (user_request or "").strip()
            extracted_symbols: List[str] = []

            runtime = get_runtime(AgentContext)
            context = runtime.context
            portfolio_model = context.get("portfolio_model", LLMModel.GPT4oMini)
            llm = self._llm_factory(portfolio_model)
            chain = prompt | llm.with_structured_output(QueryTypeResult)

            try:
                query_type = chain.invoke({"user_query": user_query}) if user_query else None
            except Exception as exc:  # pragma: no cover - LLM/parsing issues
                logger.error("Query type classification failed: %s", exc, exc_info=True)
                query_type = None

            if query_type and query_type.query_type == "specific_stocks_scope":
                extracted_symbols = get_symbol_names(user_query)

                logger.info("Extracted symbols: %s", extracted_symbols)
                summary = (
                    f"Identified symbols: {', '.join(extracted_symbols)}"
                    if extracted_symbols
                    else "No valid symbols detected in the user request."
                )
                symbol_message = AIMessage(content=summary, name="portfolio_symbol_extractor")

            else:
                summary = "User is asking about the entire portfolio"
                symbol_message = AIMessage(content=summary, name="portfolio_symbol_extractor")

            return {
                **state,
                "messages": messages + [symbol_message],
                "symbol_names": extracted_symbols,
            }

        return RunnableLambda(portfolio_node_fn)
