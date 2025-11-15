import json
from typing import List
import pandas as pd
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda

from src.core.enums import LLMModel


class PortfolioContextLoaderNode:
    """Loads portfolio context (currently from portfolio.xlsx)."""

    def get_runnable_sequence(self, model: LLMModel):
        def _load(msgs: List[BaseMessage]):
            # Detect if reasoning requested portfolio data (optional: trust and always load)
            portfolio_data = []
            try:
                df = pd.read_excel("portfolio.xlsx")
                def pick(cols, default=None):
                    for c in cols:
                        if c in df.columns:
                            return c
                    return default
                sym_col = pick(["Symbol", "SYMBOL", "Ticker", "TICKER"])
                qty_col = pick(["Quantity Available", "Quantity", "QTY", "qty", "quantity"])
                buy_col = pick(["Average Price", "Avg Price", "avg_price", "BUY_PRICE", "Buy Price"])
                sec_col = pick(["Sector", "SECTOR", "sector"])
                for _, row in df.iterrows():
                    item = {
                        "symbol": str(row[sym_col]).strip() if sym_col else None,
                        "quantity": float(row[qty_col]) if qty_col else None,
                        "buy_price": float(row[buy_col]) if buy_col else None,
                    }
                    if sec_col:
                        item["sector"] = str(row[sec_col]).strip()
                    portfolio_data.append(item)
                portfolio_data = [x for x in portfolio_data if x.get("symbol")]
            except Exception:
                portfolio_data = []
            return [AIMessage(content=json.dumps({"portfolio_data": portfolio_data}), name="context_loader")]

        return RunnableLambda(_load)
