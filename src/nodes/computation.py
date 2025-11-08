"""Computation agent node for financial computations."""

from typing import Final

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from src.core.enums import LLMModel
from src.schemas.computation import ComputationQuery
from src.tools.calculate_profit_tool import calculate_profit
from src.tools.get_row_tool import get_entire_row
from src.tools.get_symbol_name import get_symbol_name
from src.tools.get_ticker_price import get_ticker_price


class ComputationNode:
    """Computation agent node for financial computations."""

    _SYSTEM_PROMPT: Final[
        str
    ] = """
    You are a financial assistant.
    Use the tools provided to answer the question
    Always use get_symbol_name tool first to get the stock symbol from the user's question.
    """

    def __init__(self):
        """
        Initialize the ComputationNode.
        """

    def get_agent(self, model: LLMModel):
        """
        Get the agent instance.

        Args:
            model: The model to use for the agent

        Returns:
            The initialized agent
        """
        self.agent = create_agent(
            model=model.value,
            tools=[get_ticker_price, get_symbol_name, calculate_profit, get_entire_row],
            response_format=ToolStrategy(ComputationQuery),
            system_prompt=self._SYSTEM_PROMPT,
        )
        return self.agent
