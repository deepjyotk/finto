"""LangChain agent with a yfinance tool to fetch ticker prices.

Provides a simple `query(question: str) -> str` function that runs the
agent (which has access to a `get_ticker_price` tool).
"""
import os
from dotenv import load_dotenv

from langchain_openai.chat_models import ChatOpenAI
from langchain.agents import create_agent

import yfinance as yf

# load environment
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


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
    tools=[get_ticker_price]
)



def query(question: str) -> str:
    """Run the agent on the provided question and return its textual result.

    Raises RuntimeError if OPENAI_API_KEY is not configured or the agent fails.
    """
    if not isinstance(question, str) or not question.strip():
        return "Error: question must be a non-empty string"

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Set it in the environment or .env file")

    try:
        return str(_agent.invoke( {"messages": [{"role": "user", "content": question}] }))
    except Exception as e:
        raise RuntimeError(f"Agent run failed: {e}") from e