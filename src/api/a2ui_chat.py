"""A2UI chat API router.

Exposes ``POST /a2ui/chat`` as a Server-Sent Events (SSE) endpoint that
streams structured A2UI events from the LangGraph agent.

This endpoint is the A2UI-path counterpart to the TheSys ``/thesys/chat``
endpoint.  It is only active when ``THESYS_ENABLED=false``; if TheSys is
enabled the endpoint returns 503 with a clear message so misconfigured
clients fail loudly.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.a2ui.sse_emitter import a2ui_sse_generator
from src.api.schemas.thesys_chat import C1ChatRequest
from src.billing.langsmith_tracker import CreditTrackingCallback
from src.core.db import SessionLocal
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.core.settings import thesys_settings
from src.dependencies import get_a2ui_chat_service
from src.services.a2ui_chat_service import A2UIChatService

logger = logger_for("api.a2ui_chat")
router = APIRouter(prefix="/a2ui", tags=["a2ui-chat"])


@router.post(
    "/chat",
    summary="Streaming A2UI chat endpoint",
    description=(
        "Server-Sent Events endpoint that streams structured A2UI events "
        "(step_start, tool_call, message_chunk, etc.) for the current agent turn. "
        "Active only when THESYS_ENABLED=false."
    ),
)
async def a2ui_chat(
    request: C1ChatRequest,
    a2ui_service: A2UIChatService = Depends(get_a2ui_chat_service),
    user: dict = Depends(require_auth),
):
    """Stream A2UI events for one chat turn."""
    if thesys_settings.thesys_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "A2UI endpoint is disabled because THESYS_ENABLED=true. "
                "Use /api/v1/thesys/chat instead."
            ),
        )

    user_id = uuid.UUID(user["user_id"])

    logger.info(
        "a2ui_chat_request",
        extra={
            "session_id": request.session_id,
            "user_id": str(user_id),
        },
    )

    db = SessionLocal()
    credit_callback = CreditTrackingCallback(user_id, db)

    async def _event_stream():
        try:
            async for event in a2ui_service.stream(
                request, user_id=user_id, callbacks=[credit_callback]
            ):
                yield event
        finally:
            try:
                await credit_callback.finalize_and_save()
                usage = credit_callback.get_summary()
                logger.info(
                    f"[A2UI] Completed — tokens: {usage['total_tokens']}, "
                    f"credits: {usage['total_credits_deducted']}"
                )
            except Exception as billing_exc:
                logger.warning(f"[A2UI] Credit finalization failed: {billing_exc}")
            finally:
                await db.close()

    return StreamingResponse(
        a2ui_sse_generator(_event_stream()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
