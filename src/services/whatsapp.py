"""WhatsApp service - pure class for business logic, no FastAPI imports"""

import asyncio
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus
from uuid import UUID

import httpx

from src.api.schemas.chat import ChatRequest
from src.api.schemas.whatsapp import WhatsAppWebhook
from src.core.json_logging import logger_for
from src.core.schema import AgentMessage
from src.core.settings import whatsapp_settings
from src.models.whatsapp_metadata import WhatsAppMetadata
from src.repositories.whatsapp_repo import WhatsAppRepository
from src.services.chat import ChatService

logger = logger_for(__name__)


class WhatsAppService:
    """Service layer for WhatsApp operations"""

    def __init__(self, repo: WhatsAppRepository, chat_service: ChatService):
        """
        Initialize WhatsAppService.

        Args:
            repo: WhatsAppRepository instance for data access
        """
        self.repo = repo
        self.chat_service = chat_service

    @staticmethod
    def _rand_code(n: int = 6) -> str:
        """
        Generate a random alphanumeric code.

        Args:
            n: Length of the code (default: 6)

        Returns:
            Random alphanumeric code string
        """
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(n))

    async def create_connect_intent(
        self, user_id: UUID, ttl_minutes: int = 10
    ) -> tuple[str, str, datetime]:
        """
        Create a WhatsApp connect intent.

        This generates a temporary code, stores it in the database,
        and returns the code, deeplink, and expiration time.

        Args:
            user_id: UUID of the user
            ttl_minutes: Time to live in minutes (default: 10)

        Returns:
            Tuple of (code, deeplink, expires_at)
        """
        # Generate random code
        code = self._rand_code()

        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        # Store in database
        await self.repo.add(user_id=user_id, temporary_code=code)
        await self.repo.session.commit()

        # Generate deeplink
        sender = whatsapp_settings.wa_sender_e164
        text = f"START {code}"
        deeplink = f"https://wa.me/{sender}?text={quote_plus(text)}"

        return (code, deeplink, expires_at)

    async def send_template(
        self,
        to: str,
        name: str,
        language: str = "en_US",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Send a WhatsApp template message.

        This method sends a template message to a WhatsApp user via the
        Facebook Graph API.

        Args:
            to: E.164 phone number of the recipient
            name: Template name
            language: Language code (default: "en_US")
            components: List of template components (default: None)

        Returns:
            Response dictionary from the API

        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        url = (
            f"https://graph.facebook.com/{whatsapp_settings.wa_api_version}/"
            f"{whatsapp_settings.wa_phone_number_id}/messages"
        )

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": name,
                "language": {"code": language},
                "components": components or [],
            },
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {whatsapp_settings.wa_user_or_system_token}"
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def send_text(
        self,
        to: str,
        text: str,
        preview_url: bool = False,
    ) -> dict[str, Any]:
        """
        Send a WhatsApp text message.

        This method sends a text message to a WhatsApp user via the
        Facebook Graph API.

        Args:
            to: E.164 phone number of the recipient
            text: Message text content
            preview_url: Whether to enable URL preview (default: False)

        Returns:
            Response dictionary from the API

        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        url = (
            f"https://graph.facebook.com/{whatsapp_settings.wa_api_version}/"
            f"{whatsapp_settings.wa_phone_number_id}/messages"
        )

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"preview_url": preview_url, "body": text},
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {whatsapp_settings.wa_user_or_system_token}"
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_whatsapp_data_by_user_id(
        self, user_id: UUID
    ) -> dict[str, Any] | None:
        """
        Get WhatsApp metadata for a user.

        Args:
            user_id: UUID of the user

        Returns:
            Dictionary with WhatsApp data if found, None otherwise
        """
        metadata = await self.repo.get_metadata_by_user_id(user_id)
        if not metadata:
            return None

        return {
            "id": str(metadata.id),
            "user_e164": metadata.user_e164,
        }

    async def delete_integration(self, integration_id: UUID, user_id: UUID) -> None:
        """
        Delete a WhatsApp integration by ID.

        Args:
            integration_id: UUID of the WhatsApp metadata entry to delete
            user_id: UUID of the user requesting the deletion

        Raises:
            ValueError: If the integration does not exist or does not belong to the user
        """
        # Check if the integration exists
        metadata = await self.repo.get_metadata_by_id(integration_id)
        if not metadata:
            raise ValueError(f"WhatsApp integration with ID {integration_id} not found")

        # Verify that the integration belongs to the user
        if metadata.user_id != user_id:
            raise ValueError(
                f"WhatsApp integration with ID {integration_id} does not belong to the user"
            )

        # Delete the metadata entry
        await self.repo.delete_metadata_by_id(integration_id)
        await self.repo.session.commit()

    async def _registered_user_message_handling(
        self, metadata: WhatsAppMetadata, message_text: str, message_from_e164: str
    ) -> None:
        """Handle incoming messages for registered users."""
        if not message_text.strip():
            logger.debug(
                "Skipping empty or non-text message for user %s", metadata.user_id
            )
            await self.send_text(
                to=message_from_e164,
                text="I can currently process text messages only. Please send a new message.",
            )
            return

        user_id = metadata.user_id
        logger.debug(f"Registered user {user_id} sent: {message_text}")

        session = await self.repo.get_active_session_by_user_id(user_id)
        if session:
            session_id = str(session.session_id)
            logger.debug(
                "Found active chat session %s for user %s", session_id, user_id
            )
        else:
            session = await self.repo.create_chat_session(user_id)
            await self.repo.session.commit()
            session_id = str(session.session_id)
            logger.info("Created new chat session %s for user %s", session_id, user_id)

        try:
            chat_request = ChatRequest(message=message_text)
            response = await self.chat_service.query(
                chat_request,
                session_id,
                user_id,
            )
            if isinstance(response, AgentMessage):
                response_text = response.content
            elif response is None:
                response_text = ""
            else:
                response_text = str(response)
        except Exception as e:
            logger.error(f"Error processing chat session: {e}")
            response_text = (
                "Sorry, I wasn't able to generate a response. Please try again."
            )

        if not response_text:
            response_text = (
                "Sorry, I wasn't able to generate a response. Please try again."
            )

        await self.send_text(
            to=message_from_e164,
            text=response_text,
        )

    async def _unregistered_user_message_handling(
        self, message_text: str, message_from_e164: str
    ) -> None:
        """Handle incoming messages for unregistered users."""
        if message_text.strip().upper().startswith("START "):
            parts = message_text.strip().split()
            if len(parts) >= 2:
                code = parts[1].upper()

                cache_entry = await self.repo.by_temporary_code(code)

                if cache_entry:
                    created_at_utc = cache_entry.created_at.replace(tzinfo=timezone.utc)
                    expires_at = created_at_utc + timedelta(minutes=10)
                    now = datetime.now(timezone.utc)

                    if now > expires_at:
                        await self.repo.delete_cache_entry(cache_entry.id)
                        await self.repo.session.commit()

                        await self.send_text(
                            to=message_from_e164,
                            text="Your registration code has expired. Please visit the website to generate a new code.",
                        )
                    else:
                        await self.send_text(
                            to=message_from_e164,
                            text="Successfully registered! You can now start chatting with us.",
                        )
                        await self.repo.create_metadata(
                            user_id=cache_entry.user_id,
                            user_e164=message_from_e164,
                        )
                        await self.repo.delete_cache_entry(cache_entry.id)
                        await self.repo.session.commit()
                else:
                    await self.send_text(
                        to=message_from_e164,
                        text="Invalid code. Please visit the website to generate a new registration code.",
                    )
            else:
                await self.send_text(
                    to=message_from_e164,
                    text="Invalid format. Please send 'START <CODE>' where <CODE> is the code from the website.",
                )
        else:
            await self.send_text(
                to=message_from_e164,
                text="Welcome! To get started, please visit our website to generate a registration code, then send 'START <CODE>' here.",
            )

    async def _background_read_and_typing(self, to: str, message_id: str) -> None:
        """
        Fire-and-forget: mark as read + send typing.
        Failures are logged but never raised.
        """
        try:
            await self.mark_message_as_read(message_id)
        except Exception as e:
            logger.warning("Failed to mark message %s as read: %s", message_id, e)

        try:
            await self.send_typing_indicator(
                to=to,
                message_id=message_id,
            )
        except Exception as e:
            logger.warning("Failed to send typing indicator for %s: %s", message_id, e)

    async def process_webhook(self, webhook_data: WhatsAppWebhook):
        """
        Process incoming WhatsApp webhook data.

        This method processes webhook entries, handling messages and statuses
        from WhatsApp Business API.

        Args:
            webhook_data: Validated WhatsApp webhook data

        Returns:
            Dictionary with processing result
        """

        # Optionally: send typing indicator while we process
        try:
            for entry in webhook_data.entry:
                for change in entry.changes:
                    value = change.value
                    if value.messages:
                        for msg in value.messages:
                            # Process incoming messages
                            message_text = msg.text.body if msg.text else ""
                            msg.timestamp
                            msg.type
                            message_from_e164 = msg.from_

                            logger.info(
                                f"Processing message from {message_from_e164} with text: {message_text}"
                                f"Message ID: {msg.id}"
                            )

                            # 🔥 Fire-and-forget: don't block main logic
                            asyncio.create_task(
                                self._background_read_and_typing(
                                    to=message_from_e164, message_id=msg.id
                                )
                            )

                            # Check if user is already registered in whatsapp_metadata
                            metadata = await self.repo.get_metadata_by_e164(
                                message_from_e164
                            )

                            if metadata:
                                logger.debug(
                                    f"User {message_from_e164} is already registered in whatsapp_metadata"
                                )
                                await self._registered_user_message_handling(
                                    metadata, message_text, message_from_e164
                                )
                            else:
                                await self._unregistered_user_message_handling(
                                    message_text, message_from_e164
                                )
            return {"status": "processed"}
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            raise e

    async def mark_message_as_read(self, message_id: str) -> None:
        """
        Mark an incoming WhatsApp message as read (Cloud API).
        """
        url = (
            f"https://graph.facebook.com/{whatsapp_settings.wa_api_version}/"
            f"{whatsapp_settings.wa_phone_number_id}/messages"
        )

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                response = await client.post(  # <-- POST, **not** PUT
                    url,
                    headers={
                        "Authorization": f"Bearer {whatsapp_settings.wa_user_or_system_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Failed to mark message as read - HTTP error: "
                    "message_id=%s, status_code=%s, response_text=%s, url=%s",
                    message_id,
                    exc.response.status_code,
                    exc.response.text,
                    url,
                )
                # In fire-and-forget we *don't* want to crash anything, so just return
            except Exception as exc:
                logger.error(
                    "Failed to mark message as read - unexpected error: "
                    "message_id=%s, error=%s, url=%s",
                    message_id,
                    exc,
                    url,
                )

    async def send_typing_indicator(
        self,
        to: str,
        message_id: str,
    ) -> dict[str, Any]:
        """
        Send a typing indicator (and optionally a read receipt) for a message.

        Args:
            to: Recipient's E.164 phone number
            message_id: The WhatsApp message ID (wamid...) you are replying to

        Returns:
            Response dictionary from the API
        """
        url = (
            f"https://graph.facebook.com/{whatsapp_settings.wa_api_version}/"
            f"{whatsapp_settings.wa_phone_number_id}/messages"
        )

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            # Depending on Meta's docs you might not need "type"/"status" here,
            # but this shape is close to what they describe. The key bit is:
            # typing_indicator.type MUST be "TEXT".
            "typing_indicator": {
                "type": "TEXT",  # <- REQUIRED ENUM VALUE
            },
            "status": "read",
            "message_id": message_id,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {whatsapp_settings.wa_user_or_system_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Failed to send typing indicator - HTTP error: "
                    "to=%s, message_id=%s, "
                    "status_code=%s, response_text=%s, url=%s",
                    to,
                    message_id,
                    exc.response.status_code,
                    exc.response.text,
                    url,
                )
                raise
            except Exception as exc:
                logger.error(
                    "Failed to send typing indicator - unexpected error: "
                    "to=%s, message_id=%s, error=%s, url=%s",
                    to,
                    message_id,
                    exc,
                    url,
                )
                raise
