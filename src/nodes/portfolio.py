"""Portfolio symbol extraction node."""

from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, ValidationError

from src.core.json_logging import logger_for
from src.schemas.agent_state import AgentState
from src.tools.get_symbol_name import get_symbol_names

logger = logger_for(__name__)


class SymbolExtractionResult(BaseModel):
    """Pydantic model for validating symbol extraction output."""

    symbol_names: List[str]


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

        def portfolio_node_fn(state: AgentState) -> AgentState:
            messages = state.get("messages", [])
            user_request = state.get("user_request") or self._latest_user_message_content(messages)

            user_query = (user_request or "").strip()

            if not user_query:
                logger.warning("Portfolio node invoked without a user request")
                extracted_symbols: List[str] = []
            else:
                try:
                    tool_response = get_symbol_names.invoke({"user_query": user_query})
                except Exception as exc:  # pragma: no cover - tool level errors
                    logger.error("get_symbol_names tool failed: %s", exc, exc_info=True)
                    tool_response = []
                try:
                    parsed = SymbolExtractionResult(symbol_names=list(tool_response or []))
                    extracted_symbols = [
                        symbol for symbol in parsed.symbol_names if isinstance(symbol, str)
                    ]
                except ValidationError as exc:
                    logger.error(
                        "Unable to parse symbol extraction response: %s", exc, exc_info=True
                    )
                    extracted_symbols = []

            logger.info("Extracted symbols: %s", extracted_symbols)
            summary = (
                f"Identified symbols: {', '.join(extracted_symbols)}"
                if extracted_symbols
                else "No valid symbols detected in the user request."
            )
            symbol_message = AIMessage(content=summary, name="portfolio_symbol_extractor")

            return {
                **state,
                "messages": messages + [symbol_message],
                "symbol_names": extracted_symbols,
            }

        return RunnableLambda(portfolio_node_fn)
