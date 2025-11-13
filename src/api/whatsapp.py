import hashlib
import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from src.api.schemas.whatsapp import (
    ConnectIntentRequest,
    ConnectIntentResponse,
    SendTemplateRequest,
    SendTemplateResponse,
    SendTextRequest,
    SendTextResponse,
    WhatsAppWebhook,
)
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.core.settings import whatsapp_settings
from src.dependencies import get_whatsapp_service
from src.services.whatsapp import WhatsAppService

router = APIRouter(prefix="", tags=["whatsapp"])

logger = logger_for(__name__)


@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
async def verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    mode: str | None = None,
    challenge: str | None = None,
    verify_token: str | None = None,
):
    try:
        mode = mode or hub_mode
        challenge = challenge or hub_challenge
        token = verify_token or hub_verify_token
        if mode == "subscribe" and token == whatsapp_settings.wa_verify_token:
            return challenge or ""
        raise HTTPException(status_code=403, detail="Verification failed")
    except Exception as e:
        logger.error(f"Error verifying webhook: {e}")
        return PlainTextResponse(status_code=e.status_code, content=str(e))


def _check_signature(raw_body: bytes, signature_header: str | None) -> None:
    if not whatsapp_settings.wa_app_secret or not signature_header:
        return
    expected = (
        "sha256="
        + hmac.new(whatsapp_settings.wa_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    )
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Bad signature")


@router.post("/webhooks/whatsapp")
async def receive(
    request: Request,
    svc: Annotated[WhatsAppService, Depends(get_whatsapp_service)],
):
    try:
        raw = await request.body()
        _check_signature(raw, request.headers.get("X-Hub-Signature-256"))
        webhook_data = WhatsAppWebhook.model_validate_json(raw)
    except Exception as e:
        logger.error(f"Validation error: {e}")
        logger.error(f"RAW: {raw[:500]}")
        return PlainTextResponse(status_code=400, content="Validation error")

    try:
        # Use service to process webhook
        result = await svc.process_webhook(webhook_data=webhook_data)
        logger.info("Webhook processed successfully")
        return result
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Return ok to prevent webhook retries for processing errors
        return {"ok": True}


@router.post("/api/whatsapp/send-text", response_model=SendTextResponse)
async def send_text(
    body: SendTextRequest,
    svc: Annotated[WhatsAppService, Depends(get_whatsapp_service)],
):
    try:
        # Use service to send text
        response = await svc.send_text(
            to=body.to,
            text=body.text,
        )

        logger.info(f"Text sent successfully: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending text: {e}")
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.post("/api/whatsapp/send-template", response_model=SendTemplateResponse)
async def send_template(
    body: SendTemplateRequest,
    svc: Annotated[WhatsAppService, Depends(get_whatsapp_service)],
):
    # user_id = UUID(user["user_id"])
    try:
        # Use service to send template
        components = [c.model_dump() for c in body.components]
        response = await svc.send_template(
            to=body.to,
            name=body.name,
            language=body.language,
            components=components,
        )

        logger.info(f"Template sent successfully: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending template: {e}")
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.post("/api/whatsapp/connect-intent", response_model=ConnectIntentResponse)
async def create_connect_intent(
    body: ConnectIntentRequest,
    svc: Annotated[WhatsAppService, Depends(get_whatsapp_service)],
    user: dict = Depends(require_auth),
):
    user_id = UUID(user["user_id"])
    try:
        # Use service to create connect intent
        code, deeplink, expires_at = await svc.create_connect_intent(
            user_id=user_id, ttl_minutes=body.ttl_minutes or 10
        )

        logger.info(f"Connect intent created successfully: {code}, {deeplink}, {expires_at}")
        return ConnectIntentResponse(code=code, deeplink=deeplink, expires_at=expires_at)
    except Exception as e:
        logger.error(f"Error creating connect intent: {e}")
        raise HTTPException(status_code=e.status_code, detail=str(e))
