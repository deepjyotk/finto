import dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
import pandas as pd
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from dotenv import load_dotenv
from regex import D

load_dotenv()

# 1️⃣ Load your Excel file
df = pd.read_excel("portfolio.xlsx")

@tool
def get_entire_row(symbol_name: str) -> dict:
    """Extracts the entire row from the portfolio containing details regarding the stock symbol"""
    return df[df["Symbol"] == symbol_name].iloc[0].to_dict()


# llm = ChatOpenAI(model="gpt-4o", temperature=0)
# system_prompt = (
#     f"You are a financial assistant that returns the entire row from the portfolio data.\n{df.to_markdown()}\n"
# )

# # 3️⃣ Create a Pandas DataFrame agent
# agent = create_agent(llm,system_prompt=system_prompt,tools=[get_entire_row])

# raw = agent.invoke({
#     "messages": [HumanMessage(content="I want to calculate the total value of my holdings in adani green")],
# })
# print("Agent Response:", raw)

