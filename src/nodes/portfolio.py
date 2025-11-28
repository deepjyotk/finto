"""Portfolio symbol extraction node."""

from typing import List, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.runtime import get_runtime
from pydantic import BaseModel, ValidationError

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

    query_type: Literal["specific", "entire"]


class PortfolioNode:
    """Portfolio node responsible for extracting symbol names."""

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
                        "Classify the user's portfolio question.\n"
                        'Return JSON with field "query_type" set to:\n'
                        '- "specific" if the request references any ticker/symbol/company/index or asks about a subset of assets.\n'
                        '- "entire" for broad portfolio-wide questions with no specific tickers.\n'
                        "No explanations."
                    ),
                ),
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
            llm_kwargs = {"model": portfolio_model.model_name, **portfolio_model.llm_kwargs}
            llm = ChatOpenAI(**llm_kwargs)
            chain = prompt | llm.with_structured_output(QueryTypeResult)

            try:
                query_type = chain.invoke({"user_query": user_query}) if user_query else None
            except Exception as exc:  # pragma: no cover - LLM/parsing issues
                logger.error("Query type classification failed: %s", exc, exc_info=True)
                query_type = None

            if query_type and query_type.query_type == "specific":
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
