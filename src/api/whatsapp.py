import asyncio
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
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
from src.core.db import SessionLocal
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.core.settings import whatsapp_settings
from src.dependencies import get_whatsapp_service
from src.repositories.whatsapp_repo import WhatsAppRepository
from src.services.chat import ChatService
from src.services.whatsapp import WhatsAppService

router = APIRouter(prefix="", tags=["whatsapp"])

logger = logger_for(__name__)


async def _process_webhook_background(webhook_data: WhatsAppWebhook) -> None:
    """
    Process webhook in background with its own database session.

    This function creates a new session and service instance to avoid
    using a session from the request lifecycle that gets closed.
    """
    async with SessionLocal() as session:
        try:
            repo = WhatsAppRepository(session)
            chat_service = ChatService()
            svc = WhatsAppService(repo=repo, chat_service=chat_service)
            await svc.process_webhook(webhook_data=webhook_data)
        except Exception as e:
            logger.exception(f"Error processing webhook in background: {e}")
        finally:
            await session.rollback()


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


MAX_EVENT_AGE = timedelta(minutes=5)


def _get_event_timestamp(webhook_data: WhatsAppWebhook) -> datetime | None:
    """
    Extract the timestamp (as UTC datetime) from the first message/status
    in the webhook. WhatsApp sends timestamp as a string of unix seconds.
    """
    try:
        entry = webhook_data.entry[0]
        change = entry.changes[0]
        value = change.value

        ts_str = None

        # Incoming user messages
        if getattr(value, "messages", None):
            ts_str = value.messages[0].timestamp

        # Status callbacks (sent/delivered/read)
        elif getattr(value, "statuses", None):
            ts_str = value.statuses[0].timestamp

        if not ts_str:
            return None

        ts_int = int(ts_str)  # "1763249605" -> 1763249605
        return datetime.fromtimestamp(ts_int, tz=timezone.utc)
    except Exception:
        # If anything is weird, just skip age filtering
        return None


@router.post("/webhooks/whatsapp")
async def receive(request: Request):
    raw = await request.body()

    try:
        # Verify signature
        _check_signature(raw, request.headers.get("X-Hub-Signature-256"))

        # Parse payload
        webhook_data = WhatsAppWebhook.model_validate_json(raw)

        # Age check: ignore very old events
        event_ts = _get_event_timestamp(webhook_data)
        if event_ts is not None:
            age = datetime.now(timezone.utc) - event_ts
            if age > MAX_EVENT_AGE:
                logger.info(
                    "Ignoring stale WhatsApp webhook "
                    f"(age={age}, event_ts={event_ts.isoformat()})"
                )
                return Response(status_code=200, content="Ignored stale webhook")

        # Process in background (don't block WhatsApp)
        asyncio.create_task(_process_webhook_background(webhook_data))

        return Response(status_code=200, content="Webhook accepted")
    except Exception:
        logger.exception("Error handling WhatsApp webhook")
        # Still return 200 so WhatsApp doesn't retry forever
        return Response(status_code=200, content="Error (logged)")


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
        return Response(status_code=500, content=str(e))


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


@router.delete("/api/whatsapp/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    svc: Annotated[WhatsAppService, Depends(get_whatsapp_service)],
    user: dict = Depends(require_auth),
):
    """
    Delete a WhatsApp integration.

    This endpoint deletes the WhatsApp metadata entry for the specified integration ID.
    Only the owner of the integration can delete it.

    **Authentication required**: Yes (JWT token in cookie)

    Returns:
        Success message upon successful deletion
    """
    user_id = UUID(user["user_id"])
    try:
        # Use service to delete integration
        await svc.delete_integration(integration_id=integration_id, user_id=user_id)

        logger.info(f"WhatsApp integration deleted successfully: {integration_id}")
        return {"message": "WhatsApp integration deleted successfully"}
    except ValueError as e:
        logger.error(f"Error deleting integration: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting integration: {e}")
        raise HTTPException(status_code=500, detail=str(e))
