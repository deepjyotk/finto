"""Service: builds the full ticker page payload."""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.json_logging import logger_for
from src.repositories.financial_statements_repo import FinancialStatementsRepo
from src.repositories.ticker_info_repo import TickerInfoRepo

logger = logger_for(__name__)

# Ordered metric rows to display (matches screener.in order)
ANNUAL_METRICS = [
    "Total Revenue",
    "Total Expenses",
    "Operating Income",
    "EBITDA",
    "Pretax Income",
    "Tax Provision",
    "Net Income",
    "Basic EPS",
    "Diluted EPS",
]

QUARTERLY_METRICS = [
    "Total Revenue",
    "Total Expenses",
    "Operating Income",
    "EBITDA",
    "Pretax Income",
    "Tax Provision",
    "Net Income",
    "Basic EPS",
]

BALANCE_SHEET_METRICS = [
    "Total Assets",
    "Total Liabilities Net Minority Interest",
    "Stockholders Equity",
    "Total Debt",
    "Net Debt",
    "Cash And Cash Equivalents",
    "Current Assets",
    "Current Liabilities",
    "Accounts Receivable",
    "Inventory",
    "Goodwill",
]

CASH_FLOW_METRICS = [
    "Operating Cash Flow",
    "Investing Cash Flow",
    "Financing Cash Flow",
    "Free Cash Flow",
    "Capital Expenditure",
    "Net Income From Continuing Operations",
    "Depreciation And Amortization",
    "Change In Working Capital",
]


class TickerService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._fin_repo = FinancialStatementsRepo(session)
        self._info_repo = TickerInfoRepo(session)

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _to_ns(symbol: str) -> str:
        s = symbol.upper().strip()
        return s if s.endswith(".NS") else f"{s}.NS"

    @staticmethod
    def _fetch_yf_info(symbol_ns: str) -> dict:
        import yfinance as yf

        ticker = yf.Ticker(symbol_ns)
        info = ticker.info or {}
        return info

    @staticmethod
    def _fetch_price_history(symbol_ns: str, period: str, interval: str) -> list[dict]:
        import yfinance as yf

        ticker = yf.Ticker(symbol_ns)
        hist = ticker.history(period=period, interval=interval, auto_adjust=True)
        if hist is None or hist.empty:
            return []
        rows = []
        for ts, row in hist.iterrows():
            rows.append(
                {
                    "date": ts.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 2) if row["Open"] else None,
                    "high": round(float(row["High"]), 2) if row["High"] else None,
                    "low": round(float(row["Low"]), 2) if row["Low"] else None,
                    "close": round(float(row["Close"]), 2) if row["Close"] else None,
                    "volume": int(row["Volume"]) if row["Volume"] else None,
                }
            )
        return rows

    @staticmethod
    def _build_statements(rows: list[dict], preferred_order: list[str]) -> dict:
        """
        Convert JSONB rows [{period, data}] into wide format for the UI table:
        { periods: [...], rows: [{metric, values: {period: value}}] }

        Input (from FinancialStatementsRepo.get_statements):
            [{"period": date(2024,3,31), "data": {"Net Income": 179181000000, ...}}, ...]

        Output (for frontend table):
            {
                "periods": ["2020-03-31", "2021-03-31", ...],
                "rows": [
                    {"metric": "Net Income", "values": {"2020-03-31": 45000000000, ...}},
                    ...
                ]
            }
        """
        from collections import defaultdict

        by_metric: dict[str, dict[str, float | None]] = defaultdict(dict)
        periods_set: set[str] = set()

        for r in rows:
            period_str = (
                r["period"].isoformat() if isinstance(r["period"], date) else str(r["period"])
            )
            periods_set.add(period_str)
            for metric, val in (r["data"] or {}).items():
                by_metric[metric][period_str] = float(val) if val is not None else None

        periods = sorted(periods_set)

        # Order rows: preferred metrics first, then remaining alphabetically
        ordered = [m for m in preferred_order if m in by_metric]
        rest = sorted([m for m in by_metric if m not in preferred_order])
        ordered.extend(rest)

        rows_out = []
        for metric in ordered:
            values = {p: by_metric[metric].get(p) for p in periods}
            rows_out.append({"metric": metric, "values": values})

        return {"periods": periods, "rows": rows_out}

    @staticmethod
    def _extract_key_ratios(info: dict) -> list[dict]:
        """Map yfinance info dict to the key ratio tiles."""

        def fmt_cr(v) -> str | None:
            """Convert raw INR to Crores."""
            try:
                return f"{v / 1e7:,.0f}"
            except (TypeError, ValueError):
                return None

        def fmt_pct(v) -> str | None:
            try:
                return f"{v * 100:.2f}"
            except (TypeError, ValueError):
                return None

        def fmt_num(v, decimals=2) -> str | None:
            try:
                return f"{v:,.{decimals}f}"
            except (TypeError, ValueError):
                return None

        mktcap = info.get("marketCap")
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        high52 = info.get("fiftyTwoWeekHigh")
        low52 = info.get("fiftyTwoWeekLow")

        ratios = [
            {"label": "Market Cap", "value": fmt_cr(mktcap), "unit": "Cr."},
            {"label": "Current Price", "value": fmt_num(price, 0), "unit": "₹"},
            {
                "label": "52W High / Low",
                "value": f"{fmt_num(high52, 0)} / {fmt_num(low52, 0)}" if high52 else None,
                "unit": "₹",
            },
            {"label": "P/E Ratio", "value": fmt_num(info.get("trailingPE")), "unit": None},
            {"label": "Book Value", "value": fmt_num(info.get("bookValue")), "unit": "₹"},
            {"label": "Dividend Yield", "value": fmt_pct(info.get("dividendYield")), "unit": "%"},
            {"label": "ROCE", "value": fmt_pct(info.get("returnOnAssets")), "unit": "%"},
            {"label": "ROE", "value": fmt_pct(info.get("returnOnEquity")), "unit": "%"},
            {
                "label": "Face Value",
                "value": fmt_num(info.get("faceValue") or info.get("priceToBook")),
                "unit": "₹",
            },
        ]
        return ratios

    # ── public ───────────────────────────────────────────────────────────

    async def get_ticker(
        self,
        symbol: str,
        price_period: str = "1y",
        price_interval: str = "1d",
        annual_periods: int = 10,
        quarterly_periods: int = 12,
    ) -> dict | None:
        equity = await self._info_repo.get_equity(symbol)
        if equity is None:
            return None

        bare = equity["symbol"]
        symbol_ns = f"{bare}.NS"
        in_equity_id = equity["id"]

        loop = asyncio.get_event_loop()

        # Fetch yf info + price history in executor (blocking IO)
        info, price_history = await asyncio.gather(
            loop.run_in_executor(None, self._fetch_yf_info, symbol_ns),
            loop.run_in_executor(
                None, self._fetch_price_history, symbol_ns, price_period, price_interval
            ),
        )

        if not info and not price_history:
            return None

        # Fetch all statement types sequentially — asyncio Sessions are not safe
        # for concurrent use; two gather'd coroutines on the same session
        # cause IllegalStateChangeError.
        annual_rows = await self._fin_repo.get_income_statements(in_equity_id, "annual", annual_periods)
        quarterly_rows = await self._fin_repo.get_income_statements(
            in_equity_id, "quarterly", quarterly_periods
        )
        annual_balance_rows = await self._fin_repo.get_balance_sheets(in_equity_id, "annual", annual_periods)
        quarterly_balance_rows = await self._fin_repo.get_balance_sheets(
            in_equity_id, "quarterly", quarterly_periods
        )
        annual_cashflow_rows = await self._fin_repo.get_cash_flows(in_equity_id, "annual", annual_periods)
        quarterly_cashflow_rows = await self._fin_repo.get_cash_flows(
            in_equity_id, "quarterly", quarterly_periods
        )
        ticker_info = await self._info_repo.get_info(symbol_ns)

        annual_stmts = self._build_statements(annual_rows, ANNUAL_METRICS)
        quarterly_stmts = self._build_statements(quarterly_rows, QUARTERLY_METRICS)
        annual_balance_stmts = self._build_statements(annual_balance_rows, BALANCE_SHEET_METRICS)
        quarterly_balance_stmts = self._build_statements(
            quarterly_balance_rows, BALANCE_SHEET_METRICS
        )
        annual_cashflow_stmts = self._build_statements(annual_cashflow_rows, CASH_FLOW_METRICS)
        quarterly_cashflow_stmts = self._build_statements(
            quarterly_cashflow_rows, CASH_FLOW_METRICS
        )

        company = {
            "symbol": bare,
            "symbol_ns": symbol_ns,
            "company_name": info.get("longName") or info.get("shortName") or bare,
            "isin": None,
            "sector": info.get("sector"),
            "website": info.get("website"),
            "current_price": info.get("regularMarketPrice") or info.get("currentPrice"),
            "currency": info.get("currency", "INR"),
            "exchange": "NSE",
        }

        return {
            "company": company,
            "key_ratios": self._extract_key_ratios(info),
            "price_history": price_history,
            "annual_pnl": {
                "statement_type": "annual",
                "periods": annual_stmts["periods"],
                "rows": annual_stmts["rows"],
            },
            "quarterly_pnl": {
                "statement_type": "quarterly",
                "periods": quarterly_stmts["periods"],
                "rows": quarterly_stmts["rows"],
            },
            "annual_balance_sheet": {
                "statement_type": "annual",
                "periods": annual_balance_stmts["periods"],
                "rows": annual_balance_stmts["rows"],
            },
            "quarterly_balance_sheet": {
                "statement_type": "quarterly",
                "periods": quarterly_balance_stmts["periods"],
                "rows": quarterly_balance_stmts["rows"],
            },
            "annual_cash_flow": {
                "statement_type": "annual",
                "periods": annual_cashflow_stmts["periods"],
                "rows": annual_cashflow_stmts["rows"],
            },
            "quarterly_cash_flow": {
                "statement_type": "quarterly",
                "periods": quarterly_cashflow_stmts["periods"],
                "rows": quarterly_cashflow_stmts["rows"],
            },
            "ticker_info": ticker_info,
        }
