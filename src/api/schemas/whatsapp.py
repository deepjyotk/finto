from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# Webhook Receive Schemas
class WhatsAppProfile(BaseModel):
    name: str


class WhatsAppContact(BaseModel):
    profile: WhatsAppProfile
    wa_id: str


class WhatsAppTextMessage(BaseModel):
    body: str


class WhatsAppMessage(BaseModel):
    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: Literal["text", "image", "video", "audio", "document", "sticker", "location", "contacts"]
    text: Optional[WhatsAppTextMessage] = None


class WhatsAppMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: Optional[List[WhatsAppContact]] = None
    messages: Optional[List[WhatsAppMessage]] = None
    statuses: Optional[List[dict]] = None


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]


class WhatsAppWebhook(BaseModel):
    object: str
    entry: List[WhatsAppEntry]


# Send Text Schemas
class SendTextRequest(BaseModel):
    to: str = Field(..., description="E.164 phone number")
    text: str


class SendTextResponse(BaseModel):
    messaging_product: str
    contacts: List[dict]
    messages: List[dict]


# Send Template Schemas
class TemplateParameter(BaseModel):
    type: str
    text: str


class TemplateComponent(BaseModel):
    type: str
    parameters: List[TemplateParameter]


class SendTemplateRequest(BaseModel):
    to: str = Field(..., description="E.164 phone number")
    name: str = Field(..., description="Template name")
    language: str = Field(default="en_US", description="Language code")
    components: List[TemplateComponent] = Field(default_factory=list)


class SendTemplateResponse(BaseModel):
    messaging_product: str
    contacts: List[dict]
    messages: List[dict]

