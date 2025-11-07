"""LangChain agent with a yfinance tool to fetch ticker prices.

Provides a simple `query(question: str) -> str` function that runs the
agent (which has access to a `get_ticker_price` tool).
"""
import os
from turtle import st
from dotenv import load_dotenv

from langchain_openai.chat_models import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import BaseTool
from urllib.parse import quote as _urlquote
from pydantic import BaseModel, Field
from langchain.agents.structured_output import ToolStrategy


from .schema import AgentMessage, AgentResponse
from .tools.get_symbol_name import get_symbol_name
from .tools.get_ticker_price import get_ticker_price
from .tools.get_row_tool import get_entire_row
from .tools.calculate_profit_tool import calculate_profit
# load environment
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class ComputationQuery(BaseModel):
    """Outputs the final computation result of the user's query."""

    computation: str = Field(
        ...,
        description="The final result of the computation that was performed.",
    )


_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)

system_prompt = (
    "You are a financial assistant."
    "Use the tools provided to answer the question"
    "Always use get_symbol_name tool first to get the stock symbol from the user's question."
)
_agent = create_agent(
    model=DEFAULT_MODEL,
    tools=[get_ticker_price, get_symbol_name,calculate_profit,get_entire_row],
    response_format=ToolStrategy(ComputationQuery),
    system_prompt=system_prompt
)


def query(question: str) -> AgentMessage:
    """Run the agent on the provided question and return the AIMessage as AgentMessage.

    Raises RuntimeError if OPENAI_API_KEY is not configured or the agent fails.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Set it in the environment or .env file")

    try:
        raw = _agent.invoke({"messages": [{"role": "user", "content": question}]})
        output = raw["structured_response"]
        return output
        #return messages[-1]
    except Exception as e:
        raise RuntimeError(f"Agent run failed: {e}") from e