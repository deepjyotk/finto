from typing import Optional

from pydantic import BaseModel


class WhatsAppPayload(BaseModel):
    """WhatsApp integration payload"""

    id: str
    user_id: str
    user_e164: str


class ChatIntegration(BaseModel):
    """Chat integration wrapper"""

    whatsapp: Optional[WhatsAppPayload] = None


class HomeFeedSchema(BaseModel):
    """Home feed response schema"""

    chat_integrations: list[ChatIntegration]

