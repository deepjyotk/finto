import hmac
import hashlib
import json
import httpx
from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import PlainTextResponse

from src.core.settings import whatsapp_settings
from src.api.schemas.whatsapp import (
    WhatsAppWebhook,
    SendTextRequest,
    SendTextResponse,
    SendTemplateRequest,
    SendTemplateResponse,
)

router = APIRouter(prefix="", tags=["whatsapp"])


@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
async def verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    mode: str | None = None,
    challenge: str | None = None,
    verify_token: str | None = None,
):
    mode = mode or hub_mode
    challenge = challenge or hub_challenge
    token = verify_token or hub_verify_token
    if mode == "subscribe" and token == whatsapp_settings.wa_verify_token:
        return challenge or ""
    raise HTTPException(status_code=403, detail="Verification failed")


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
async def receive(request: Request):
    raw = await request.body()
    _check_signature(raw, request.headers.get("X-Hub-Signature-256"))

    try:
        webhook_data = WhatsAppWebhook.model_validate_json(raw)
    except Exception as e:
        print(f"Validation error: {e}")
        print("RAW:", raw[:500])
        return {"ok": True}

    for entry in webhook_data.entry:
        for change in entry.changes:
            value = change.value

            if value.messages:
                for msg in value.messages:
                    print(
                        f"MSG from {msg.from_} ({msg.type}):", msg.text.body if msg.text else "N/A"
                    )

            if value.statuses:
                for status in value.statuses:
                    print("STATUS:", status)

    return {"ok": True}


@router.post("/api/whatsapp/send-text", response_model=SendTextResponse)
async def send_text(body: SendTextRequest):
    url = f"https://graph.facebook.com/{whatsapp_settings.wa_api_version}/{whatsapp_settings.wa_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": body.to,
        "type": "text",
        "text": {"preview_url": False, "body": body.text},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {whatsapp_settings.wa_user_or_system_token}"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()


@router.post("/api/whatsapp/send-template", response_model=SendTemplateResponse)
async def send_template(body: SendTemplateRequest):
    url = f"https://graph.facebook.com/{whatsapp_settings.wa_api_version}/{whatsapp_settings.wa_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": body.to,
        "type": "template",
        "template": {
            "name": body.name,
            "language": {"code": body.language},
            "components": [c.model_dump() for c in body.components],
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {whatsapp_settings.wa_user_or_system_token}"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()
