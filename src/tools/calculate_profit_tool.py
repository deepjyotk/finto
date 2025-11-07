import pandas as pd
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

# 1️⃣ Load your Excel file
df = pd.read_excel("portfolio.xlsx")


@tool
def calculate_profit(quantity: float, average_price: float, current_price: float) -> dict:
    """Calculates the profit or loss for a given stock position using the quantity, average purchase price, and current price."""
    profit = (current_price - average_price) * quantity
    return {"profit": profit}


# llm = ChatOpenAI(model="gpt-4o", temperature=0)
# system_prompt = (
#     f"You are a financial assistant that returns the entire row from the portfolio data.\n{df.to_markdown()}\n"
# )

# # 3️⃣ Create a Pandas DataFrame agent
# agent = create_agent(llm,system_prompt=system_prompt,tools=[calculate_profit,get_entire_row, get_symbol_name, get_ticker_price])

# raw = agent.invoke({
#     "messages": [HumanMessage(content="I want to calculate the total profit in adani green")],
# })
# print("Agent Response:", raw)
