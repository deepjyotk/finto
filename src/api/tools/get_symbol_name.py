import dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
import pandas as pd
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

class SymbolQuery(BaseModel):
    """Route a user query to the most relevant route."""

    symbol_name: str = Field(
        ...,
        description="The stock symbol relevant to the question.",
    )

# 1️⃣ Load your Excel file
df = pd.read_excel("portfolio.xlsx")
print("Portfolio Data:" , df.head())

# 2️⃣ Initialize an OpenAI chat model
llm = ChatOpenAI(model="gpt-4o", temperature=0)
system_prompt = (
    f"You are a financial assistant that answers questions about the provided portfolio data.\n{df.to_markdown()}\n"
    "Output the symbol name"
)

# 3️⃣ Create a Pandas DataFrame agent
agent = create_agent(llm,system_prompt=system_prompt, response_format=SymbolQuery)

raw = agent.invoke({
    "messages": [HumanMessage(content="I want to calculate the total value of my holdings in adani green")],
})
print("Agent Response:", raw['structured_response'].symbol_name)
# 4️⃣ Ask your question

@tool
def get_symbol_name(message: str) -> str:
    """Extract the stock symbol from the user's message."""
    return agent.invoke({
        "messages": [HumanMessage(content=message)],
    })['structured_response'].symbol_name
