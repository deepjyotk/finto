import pandas as pd
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class SymbolQuery(BaseModel):
    """Route a user query to the most relevant route."""

    symbol_name: str = Field(
        ...,
        description="The stock symbol relevant to the question.",
    )


# 1️⃣ Load your Excel file
df = pd.read_excel("portfolio.xlsx")
print("Portfolio Data:", df.head())

# 2️⃣ Initialize an OpenAI chat model
llm = ChatOpenAI(model="gpt-4o", temperature=0)
system_prompt = (
    "You are a financial assistant that answers questions about the provided portfolio data.\n"
    f"{df.to_markdown()}\n"
    "Output the symbol name."
)

# 3️⃣ Create a Pandas DataFrame agent
agent = create_agent(llm, system_prompt=system_prompt, response_format=SymbolQuery)

raw = agent.invoke(
    {
        "messages": [
            HumanMessage(
                content="I want to calculate the total value of my holdings in adani green"
            )
        ],
    }
)
print("Agent Response:", raw["structured_response"].symbol_name)
# 4️⃣ Ask your question


@tool("get_symbol_name")
def get_symbol_name(user_query: str) -> str:
    """Extracts the stock symbol from the user's query and returns the symbol name.

    Input: user's query string like "I want to calculate the total value of my holdings in adani green"
    Returns: symbol name string like "ADANIGREEN"
    """
    raw = agent.invoke(
        {
            "messages": [HumanMessage(content=user_query)],
        }
    )
    symbol_name = raw["structured_response"].symbol_name
    return symbol_name
