from datetime import datetime
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


class PortfolioUpdates(BaseModel):
    """Portfolio updates"""

    broker_id: str
    broker_name: str
    last_updated_at: datetime
    uploaded_via: str
    additional_metadata: dict[str, str]


class HoldingsMetadataSchema(BaseModel):
    """Holdings metadata response schema"""

    chat_integrations: list[ChatIntegration]
    available_brokers: list[BrokerPayload]
    portfolio_updates: list[PortfolioUpdates]
