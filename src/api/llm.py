"""LangChain agent with a yfinance tool to fetch ticker prices.

Provides a simple `query(question: str) -> str` function that runs the
agent (which has access to a `get_ticker_price` tool).
"""
import os
from dotenv import load_dotenv

from langchain_openai.chat_models import ChatOpenAI
from langchain.agents import create_agent
from pydantic import BaseModel, Field
from langchain.agents.structured_output import ToolStrategy

import yfinance as yf
from .schema import AgentMessage, AgentResponse

# load environment
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")



class StockDescription(BaseModel):
    """A stock with details."""
    symbol: str = Field(..., description="The stock symbol")
    name: str = Field(..., description="The name of the company")
    sector: str = Field(..., description="The sector the company belongs to")
    price: float = Field(..., description="The current stock price")


def get_ticker_price(ticker: str) -> str:
    """Return the latest close price for the given ticker symbol.

    Input: ticker symbol string like 'AAPL' or 'BTC-USD'.
    Output: short string with the latest close price or an error message.
    """
    if not ticker:
        return "Error: no ticker provided"
    t = ticker.strip().upper()
    try:
        hist = yf.Ticker(t).history(period="1d")
        if hist.empty:
            return f"Ticker '{t}' not found or no recent data"
        price = float(hist["Close"].iloc[-1])
        return f"{t} price: {price:.2f} USD"
    except Exception as e:
        return f"Error fetching ticker '{t}': {e}"


# Initialize LLM and agent lazily to avoid import-time failures when OPENAI_API_KEY
# is not set. We still allow import, but will raise if query() is called without a key.
_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)
_agent = create_agent(
    model=DEFAULT_MODEL,
    tools=[get_ticker_price],
    response_format=ToolStrategy(StockDescription)
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
        # messages = []
        # if hasattr(raw, "messages"):
        #     for m in getattr(raw, "messages"):
        #         content = getattr(m, "content", str(m))
        #         meta = getattr(m, "response_metadata", None)
        #         messages.append(AgentMessage(role=type(m).__name__, content=str(content), metadata=meta))
        # else:
        #     messages.append(AgentMessage(role="assistant", content=str(raw), metadata=None))

        # # Return the AIMessage produced by the agent (prefer the last AIMessage)
        # ai_messages = [m for m in messages if "AIMessage" in m.role or m.role.lower() == "assistant"]
        # if ai_messages:
        #     return ai_messages[-1]
        # # fallback to the last message
        return output
        #return messages[-1]
    except Exception as e:
        raise RuntimeError(f"Agent run failed: {e}") from e