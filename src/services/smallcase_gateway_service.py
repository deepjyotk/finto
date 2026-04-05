"""smallcase Gateway: guest JWT, holdings-import transaction, fetch holdings, portfolio analytics."""

from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
from jwt import PyJWTError

from src.core.settings import smallcase_gateway_settings

GATEWAY_TRANSACTION_BASE = "https://gatewayapi.smallcase.com/gateway"
GATEWAY_ENGINE_BASE = "https://gatewayapi.smallcase.com/v1"


def _guest_payload(ttl_seconds: int) -> dict[str, Any]:
    now = int(time.time())
    return {"guest": True, "iat": now, "exp": now + ttl_seconds}


def create_guest_auth_token() -> str:
    """JWT for Create Transaction + Gateway JS SDK init (never expose jwt_secret to the client)."""
    s = smallcase_gateway_settings
    if not s.jwt_secret:
        raise RuntimeError("SMALLCASE_GATEWAY_JWT_SECRET is not set")
    payload = _guest_payload(s.guest_token_ttl_seconds)
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def verify_connected_auth_token(token: str) -> dict[str, Any]:
    """Decode connected user token from SDK; must contain smallcaseAuthId."""
    s = smallcase_gateway_settings
    if not s.jwt_secret:
        raise RuntimeError("SMALLCASE_GATEWAY_JWT_SECRET is not set")
    try:
        decoded = jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
    except PyJWTError as exc:
        raise ValueError("Invalid or expired smallcase auth token") from exc
    if decoded.get("guest"):
        raise ValueError("Connected user token required; guest token cannot fetch holdings")
    if not decoded.get("smallcaseAuthId"):
        raise ValueError("smallcaseAuthId missing in token payload")
    return decoded


async def create_holdings_import_transaction(guest_auth_token: str) -> dict[str, Any]:
    """Create HOLDINGS_IMPORT transaction; returns transactionId and expireAt."""
    s = smallcase_gateway_settings
    if not s.is_configured:
        raise RuntimeError("smallcase Gateway is not configured")
    url = f"{GATEWAY_TRANSACTION_BASE}/{s.gateway_name}/transaction"
    headers = {
        "x-gateway-secret": s.api_secret or "",
        "x-gateway-authtoken": guest_auth_token,
        "Content-Type": "application/json",
    }
    body = {"intent": "HOLDINGS_IMPORT"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=body)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise RuntimeError(
            f"Gateway create transaction failed: {exc.response.status_code} {detail}"
        ) from exc
    data = resp.json()
    if not data.get("success"):
        errors = data.get("errors")
        raise RuntimeError(f"Gateway create transaction unsuccessful: {errors}")
    inner = data.get("data") or {}
    return {
        "transactionId": inner.get("transactionId"),
        "expireAt": inner.get("expireAt"),
    }


async def fetch_user_holdings(
    connected_auth_token: str, *, mf_holdings: bool = False
) -> dict[str, Any]:
    """GET holdings from Gateway (Holdings Import v2)."""
    s = smallcase_gateway_settings
    if not s.is_configured:
        raise RuntimeError("smallcase Gateway is not configured")
    url = f"{GATEWAY_ENGINE_BASE}/{s.gateway_name}/engine/user/holdings"
    params: dict[str, Any] = {"version": "v2"}
    if mf_holdings:
        params["mfHoldings"] = "true"
    headers = {
        "x-gateway-secret": s.api_secret or "",
        "x-gateway-authtoken": connected_auth_token,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url, headers=headers, params=params)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise RuntimeError(
            f"Gateway fetch holdings failed: {exc.response.status_code} {detail}"
        ) from exc
    return resp.json()


def _iter_security_book_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize securities from v2 / mixed API shapes into rows with name + book_cost."""
    rows: list[dict[str, Any]] = []
    raw = data.get("securities")
    if isinstance(raw, list):
        for sec in raw:
            h = sec.get("holdings") or {}
            qty = float(h.get("quantity") or 0)
            avg = float(h.get("averagePrice") or 0)
            book = qty * avg
            label = sec.get("name") or sec.get("nseTicker") or sec.get("bseTicker") or "unknown"
            rows.append(
                {"name": label, "isin": sec.get("isin"), "book_cost": book, "quantity": qty}
            )
    elif isinstance(raw, dict):
        for item in raw.get("holdings") or []:
            shares = float(item.get("shares") or item.get("quantity") or 0)
            avg = float(item.get("averagePrice") or 0)
            book = shares * avg
            label = item.get("name") or item.get("ticker") or "unknown"
            rows.append(
                {"name": label, "isin": item.get("isin"), "book_cost": book, "quantity": shares}
            )
    return rows


def _smallcase_values(data: dict[str, Any]) -> tuple[float, float]:
    """Returns (sum currentValue, sum totalReturns) for public + private smallcases where present."""
    sc = data.get("smallcases") or {}
    current_val = 0.0
    total_ret = 0.0
    for key in ("public", "private"):
        block = sc.get(key)
        if isinstance(block, list):
            for item in block:
                stats = item.get("stats") or {}
                current_val += float(stats.get("currentValue") or 0)
                total_ret += float(stats.get("totalReturns") or 0)
        elif isinstance(block, dict) and key == "private":
            stats = block.get("stats") or {}
            current_val += float(stats.get("currentValue") or 0)
            total_ret += float(stats.get("totalReturns") or 0)
    return current_val, total_ret


def _mutual_funds_book_and_marks(data: dict[str, Any]) -> tuple[float, float, int]:
    mf = data.get("mutualFunds") or {}
    holdings = mf.get("holdings") or []
    invested = 0.0
    marked = 0.0
    n = 0
    for h in holdings:
        qty = float(h.get("quantity") or 0)
        avg = float(h.get("averagePrice") or 0)
        last = h.get("lastPrice")
        invested += qty * avg
        if last is not None:
            marked += qty * float(last)
        n += 1
    return invested, marked, n


def compute_portfolio_analytics(holdings_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Investment Data Orchestrator-style summary from Gateway holdings JSON.
    Does not assume real-time equity marks unless lastPrice-like fields exist.
    """
    if not holdings_payload.get("success"):
        return {
            "ok": False,
            "error": "holdings payload indicates failure",
            "raw_errors": holdings_payload.get("errors"),
        }
    data = holdings_payload.get("data") or {}
    broker = data.get("broker")
    snapshot_date = data.get("snapshotDate") or data.get("lastUpdate")
    smallcase_auth_id = data.get("smallcaseAuthId")

    sec_rows = _iter_security_book_rows(data)
    securities_book = sum(r["book_cost"] for r in sec_rows)
    sc_value, sc_returns = _smallcase_values(data)
    mf_invested, mf_marked, mf_n = _mutual_funds_book_and_marks(data)

    # Equity book value proxy (cost basis); live market value not always in response
    total_book_securities = securities_book
    weights: list[dict[str, Any]] = []
    if sec_rows and securities_book > 0:
        for r in sec_rows:
            w = r["book_cost"] / securities_book
            weights.append(
                {
                    "name": r["name"],
                    "weight_pct": round(w * 100, 4),
                    "book_cost": round(r["book_cost"], 2),
                }
            )
        weights.sort(key=lambda x: x["weight_pct"], reverse=True)
    elif sec_rows:
        for r in sec_rows:
            weights.append(
                {"name": r["name"], "weight_pct": None, "book_cost": round(r["book_cost"], 2)}
            )

    top_holdings = weights[:10]
    hhi = 0.0
    if weights and all(x["weight_pct"] is not None for x in weights):
        hhi = sum((x["weight_pct"] / 100.0) ** 2 for x in weights)

    notes: list[str] = [
        "Equity/ETF holdings: book cost uses quantity × average price from Gateway snapshot.",
        "Live market value for direct equities not shown unless broker provides lastPrice in payload.",
    ]
    if mf_n:
        notes.append(f"Mutual funds: {mf_n} folios; marked value uses lastPrice where present.")

    return {
        "ok": True,
        "source": "smallcase_gateway",
        "broker": broker,
        "smallcase_auth_id": smallcase_auth_id,
        "snapshot_date": snapshot_date,
        "totals": {
            "securities_book_cost": round(total_book_securities, 2),
            "smallcases_marked_value": round(sc_value, 2),
            "smallcases_total_returns": round(sc_returns, 2),
            "mutual_funds_book_cost": round(mf_invested, 2),
            "mutual_funds_marked_value": round(mf_marked, 2) if mf_marked else None,
            "portfolio_book_plus_smallcases": round(
                total_book_securities + sc_value + mf_invested, 2
            ),
        },
        "risk_and_structure": {
            "concentration_hhi": round(hhi, 4) if hhi else None,
            "top_holdings_by_book_weight": top_holdings,
            "sector_allocation": "not_available_from_gateway_snapshot",
            "concentration_note": "HHI on book-cost weights; not equivalent to market-value concentration.",
        },
        "notes": notes,
    }


async def fetch_and_analyze(
    connected_auth_token: str, *, mf_holdings: bool = False
) -> dict[str, Any]:
    """Verify token, fetch holdings, compute analytics (no DB)."""
    verify_connected_auth_token(connected_auth_token)
    raw = await fetch_user_holdings(connected_auth_token, mf_holdings=mf_holdings)
    analytics = compute_portfolio_analytics(raw)
    return {"raw": raw, "analytics": analytics}
