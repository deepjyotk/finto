from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas.home import ChatIntegration, HomeFeedSchema, WhatsAppPayload
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.dependencies import get_whatsapp_service
from src.services.whatsapp import WhatsAppService

router = APIRouter(prefix="/api", tags=["home"])

logger = logger_for(__name__)


@router.get("/home", response_model=HomeFeedSchema)
async def get_home_feed(
    svc: Annotated[WhatsAppService, Depends(get_whatsapp_service)],
    user: dict = Depends(require_auth),
):
    """
    Get home feed for authenticated user.

    Returns chat integrations including WhatsApp data if available.
    """
    user_id = UUID(user["user_id"])

    try:
        # Get WhatsApp data for the user
        whatsapp_data = await svc.get_whatsapp_data_by_user_id(user_id)

        # Build chat integrations
        chat_integrations = []

        if whatsapp_data:
            # User has WhatsApp integration
            chat_integrations.append(
                ChatIntegration(
                    whatsapp=WhatsAppPayload(
                        id=whatsapp_data["id"],
                        user_id=whatsapp_data["user_id"],
                        user_e164=whatsapp_data["user_e164"],
                    )
                )
            )
        else:
            # User doesn't have WhatsApp integration yet
            chat_integrations.append(ChatIntegration(whatsapp=None))

        return HomeFeedSchema(chat_integrations=chat_integrations)

    except Exception as e:
        logger.error(f"Error getting home feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

