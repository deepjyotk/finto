from typing import Optional

from pydantic import BaseModel


class WhatsAppPayload(BaseModel):
    """WhatsApp integration payload"""

    id: str
    user_e164: str


class ChatIntegration(BaseModel):
    """Chat integration wrapper"""

    whatsapp: Optional[WhatsAppPayload] = None


class BrokerPayload(BaseModel):
    """Broker information payload"""

    broker_id: str
    broker_name: str
    broker_type: str
    country: str


class HomeFeedSchema(BaseModel):
    """Home feed response schema"""

    chat_integrations: list[ChatIntegration]
    available_brokers: list[BrokerPayload]
