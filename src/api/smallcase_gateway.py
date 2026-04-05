"""smallcase Gateway: holdings import session start + fetch holdings (logged server-side; no DB)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.core.settings import smallcase_gateway_settings
from src.services import smallcase_gateway_service as gw

logger = logger_for(__name__)

router = APIRouter(prefix="/gateway", tags=["smallcase-gateway"])


class HoldingsImportStartResponse(BaseModel):
    gateway_name: str
    guest_auth_token: str = Field(description="Guest JWT for Gateway JS SDK init only")
    transaction_id: str
    transaction_expire_at: str | None = None


class FetchHoldingsRequest(BaseModel):
    smallcase_auth_token: str = Field(
        description="Connected user JWT from Gateway SDK after successful holdings import"
    )
    mf_holdings: bool = False


@router.post(
    "/holdings-import/start",
    response_model=HoldingsImportStartResponse,
    summary="Start holdings import (create Gateway transaction)",
)
async def start_holdings_import(_user: Annotated[dict, Depends(require_auth)]):
    if not smallcase_gateway_settings.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="smallcase Gateway is not configured. Set SMALLCASE_GATEWAY_NAME, "
            "SMALLCASE_GATEWAY_API_SECRET, SMALLCASE_GATEWAY_JWT_SECRET.",
        )
    try:
        guest = gw.create_guest_auth_token()
        tx = await gw.create_holdings_import_transaction(guest)
    except RuntimeError as exc:
        logger.error("smallcase_holdings_import_start_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    tid = tx.get("transactionId")
    if not tid:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gateway did not return transactionId",
        )

    return HoldingsImportStartResponse(
        gateway_name=smallcase_gateway_settings.gateway_name or "",
        guest_auth_token=guest,
        transaction_id=tid,
        transaction_expire_at=tx.get("expireAt"),
    )


@router.post(
    "/holdings/fetch",
    summary="Fetch holdings via Gateway and log analytics (terminal / JSON logs)",
)
async def fetch_holdings_and_log(
    body: FetchHoldingsRequest,
    user: Annotated[dict, Depends(require_auth)],
) -> dict[str, Any]:
    if not smallcase_gateway_settings.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="smallcase Gateway is not configured.",
        )
    try:
        result = await gw.fetch_and_analyze(
            body.smallcase_auth_token,
            mf_holdings=body.mf_holdings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("smallcase_fetch_holdings_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    analytics = result.get("analytics") or {}
    logger.info(
        "smallcase_gateway_portfolio_snapshot",
        extra={
            "user_id": user.get("user_id"),
            "username": user.get("username"),
            "analytics": analytics,
            "broker": (result.get("raw") or {}).get("data", {}).get("broker"),
            "snapshot_date": (result.get("raw") or {}).get("data", {}).get("snapshotDate"),
        },
    )

    return {
        "success": True,
        "analytics": analytics,
        "message": "Portfolio snapshot logged server-side from smallcase Gateway (no DB write).",
    }
