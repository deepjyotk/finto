"""Kite Connect integration endpoints.

This module provides minimal endpoints to start the Kite Connect v3
authorization flow and to receive the callback. It deliberately keeps
storage of tokens in-memory as a placeholder. See TODO comments for
improvements (secure secrets, persistent storage, token refresh etc.).
"""

import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse
from kiteconnect import KiteConnect

from src.core.json_logging import logger_for
from src.core.middleware import get_current_user_optional, require_auth

logger = logger_for(__name__)
logging.basicConfig(level=logging.INFO)

# Load keys from environment where possible. Default API key set to the one
# provided in the request. IMPORTANT: do NOT commit your API secret to source.
KITE_API_KEY = os.getenv("KITE_API_KEY")
KITE_API_SECRET = os.getenv("KITE_API_SECRET")  # TODO: set this in your .env or secure vault

# Frontend base to redirect the user back to after successful/failed auth.
FRONTEND_BASE = os.getenv("FRONTEND_BASE", "http://localhost:3000")

# In-memory user -> kite token map. TODO: persist securely in DB or secrets store.
KITE_USER_TOKENS: dict[str, dict] = {}

router = APIRouter(prefix="/kite", tags=["kite"])


def _sanitize_session_data(session_data: dict) -> dict:
    """
    Convert non-JSON-native types (e.g., datetime) inside session_data to serializable values.
    TODO: Expand sanitization for Decimal or other custom types if they appear.
    """
    if not isinstance(session_data, dict):
        return session_data
    sanitized = {}
    for k, v in session_data.items():
        if isinstance(v, datetime):
            sanitized[k] = v.isoformat()
        elif isinstance(v, (list, tuple)):
            # Recursively sanitize elements
            sanitized[k] = [
                (elem.isoformat() if isinstance(elem, datetime) else elem) for elem in v
            ]
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_session_data(v)
        else:
            sanitized[k] = v
    return sanitized


@router.get("/login")
async def kite_login(user: dict = Depends(require_auth)):
    """Redirect authenticated user to Kite login page.

    The user must be logged into this application (JWT cookie). After a
    successful login on Zerodha, Zerodha will redirect to the callback URL
    configured in your Kite app settings with a request_token parameter.

    TODO: Add state parameter handling to prevent CSRF and map request -> user.
    """
    kite = KiteConnect(api_key=KITE_API_KEY)

    # KiteConnect.login_url constructs the standard login url with api_key and v=3
    login_url = kite.login_url()
    logger.info("kite_login_redirect", extra={"username": user.get("username"), "url": login_url})

    # Redirect the user's browser to Zerodha's login page
    return RedirectResponse(login_url)


@router.get("/callback")
async def kite_callback(
    request: Request, user: Optional[dict] = Depends(get_current_user_optional)
):
    # ...existing docstring...
    params = request.query_params
    status_param = params.get("status")
    request_token = params.get("request_token")

    if status_param != "success" or not request_token:
        logger.warning("kite_callback_failed", extra={"status": status_param})
        return RedirectResponse(f"{FRONTEND_BASE}/kite-connected?status=failed")

    if not KITE_API_SECRET:
        logger.error("kite_callback_no_api_secret")
        return RedirectResponse(f"{FRONTEND_BASE}/kite-connected?status=missing_api_secret")

    kite = KiteConnect(api_key=KITE_API_KEY)

    try:
        session_data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
    except Exception as exc:
        logger.error("kite_generate_session_failed", extra={"error": str(exc)})
        return RedirectResponse(f"{FRONTEND_BASE}/kite-connected?status=error")

    access_token = None
    if isinstance(session_data, dict):
        access_token = session_data.get("access_token")

    user_id = "anonymous"
    if user and user.get("user_id"):
        user_id = str(user.get("user_id"))

    # Sanitize session_data for later JSON responses
    sanitized_session = _sanitize_session_data(session_data)

    # TODO: Persist securely in DB tied to user (encrypt at rest).
    KITE_USER_TOKENS[user_id] = {
        "access_token": access_token,
        "session_data": sanitized_session,  # store sanitized version
        # TODO: store refresh metadata / re-auth strategy if needed
    }

    logger.info("kite_connected", extra={"user_id": user_id})
    return RedirectResponse(f"{FRONTEND_BASE}/kite-connected?status=success")


@router.get("/token")
async def kite_token_info(current_user: dict = Depends(require_auth)):
    """Return whether the current authenticated user has a Kite access token.
    Uses jsonable_encoder to ensure datetime (if any) is serialized.
    """
    user_id = str(current_user.get("user_id"))
    token_info = KITE_USER_TOKENS.get(user_id)
    if not token_info:
        return JSONResponse({"connected": False})
    # jsonable_encoder handles datetime safely; our session_data already sanitized.
    return JSONResponse(
        {
            "connected": True,
            "session": jsonable_encoder(token_info.get("session_data")),
            # TODO: Consider omitting sensitive fields (e.g., public_token) if not needed by frontend.
        }
    )


@router.get("/status")
async def kite_status(current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Public status endpoint for debugging.

    Returns whether the current user is connected and some non-sensitive metadata.
    """
    user_id = current_user.get("user_id") if current_user else "anonymous"
    connected = user_id in KITE_USER_TOKENS
    return {"connected": connected, "user_id": user_id}


@router.get("/holdings")
async def kite_holdings(current_user: dict = Depends(require_auth)):
    """
    Fetch user's holdings via Kite Connect.
    Requires user to have completed the auth flow (access token stored).
    TODO: Cache results (short TTL) to reduce API calls.
    """
    user_id = str(current_user.get("user_id"))
    token_info = KITE_USER_TOKENS.get(user_id)
    if not token_info or not token_info.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kite account not connected or access token missing",
        )

    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(token_info["access_token"])

    try:
        holdings = kite.holdings()
    except Exception as exc:
        logger.error("kite_holdings_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch holdings from Kite",
        )

    # Clean holdings data for JSON (in case any datetime fields appear).
    clean_holdings = jsonable_encoder(holdings)
    return {"holdings": clean_holdings}
