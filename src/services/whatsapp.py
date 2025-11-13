"""WhatsApp service - pure class for business logic, no FastAPI imports"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus
from uuid import UUID

import httpx

from src.api.schemas.whatsapp import WhatsAppWebhook
from src.core.json_logging import logger_for
from src.core.settings import whatsapp_settings
from src.repositories.whatsapp_repo import WhatsAppRepository

logger = logger_for(__name__)


class WhatsAppService:
    """Service layer for WhatsApp operations"""

    def __init__(self, repo: WhatsAppRepository):
        """
        Initialize WhatsAppService.

        Args:
            repo: WhatsAppRepository instance for data access
        """
        self.repo = repo

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
                headers={"Authorization": f"Bearer {whatsapp_settings.wa_user_or_system_token}"},
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
                headers={"Authorization": f"Bearer {whatsapp_settings.wa_user_or_system_token}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_whatsapp_data_by_user_id(self, user_id: UUID) -> dict[str, Any] | None:
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

    async def process_webhook(self, webhook_data: WhatsAppWebhook) -> dict[str, str]:
        """
        Process incoming WhatsApp webhook data.

        This method processes webhook entries, handling messages and statuses
        from WhatsApp Business API.

        Args:
            webhook_data: Validated WhatsApp webhook data

        Returns:
            Dictionary with processing result
        """
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
                            )

                            # Check if user is already registered in whatsapp_metadata
                            metadata = await self.repo.get_metadata_by_e164(message_from_e164)

                            if metadata:
                                logger.debug(
                                    f"User {message_from_e164} is already registered in whatsapp_metadata"
                                )
                                # User is already registered, process their message
                                user_id = metadata.user_id
                                logger.debug(f"Registered user {user_id} sent: {message_text}")
                            else:

                                # User is not registered, check if this is a START command
                                if message_text.strip().upper().startswith("START "):
                                    # Extract the code from message
                                    parts = message_text.strip().split()
                                    if len(parts) >= 2:
                                        code = parts[1].upper()

                                        # Look up the code in whatsapp_cache
                                        cache_entry = await self.repo.by_temporary_code(code)

                                        if cache_entry:
                                            # Check if the code has expired (10 minutes TTL)
                                            created_at_utc = cache_entry.created_at.replace(
                                                tzinfo=timezone.utc
                                            )
                                            expires_at = created_at_utc + timedelta(minutes=10)
                                            now = datetime.now(timezone.utc)

                                            if now > expires_at:
                                                # Code has expired, delete it and send re-registration template
                                                await self.repo.delete_cache_entry(cache_entry.id)
                                                await self.repo.session.commit()

                                                # Send template message to re-register
                                                await self.send_text(
                                                    to=message_from_e164,
                                                    text="Your registration code has expired. Please visit the website to generate a new code.",
                                                )
                                            else:
                                                # Code is valid, create metadata entry to link user
                                                await self.repo.create_metadata(
                                                    user_id=cache_entry.user_id,
                                                    user_e164=message_from_e164,
                                                )
                                                # Delete the cache entry after successful registration
                                                await self.repo.delete_cache_entry(cache_entry.id)
                                                await self.repo.session.commit()

                                                # Send welcome message
                                                await self.send_text(
                                                    to=message_from_e164,
                                                    text="Successfully registered! You can now start chatting with us.",
                                                )
                                        else:
                                            # Code not found
                                            await self.send_text(
                                                to=message_from_e164,
                                                text="Invalid code. Please visit the website to generate a new registration code.",
                                            )
                                    else:
                                        # Invalid START command format
                                        await self.send_text(
                                            to=message_from_e164,
                                            text="Invalid format. Please send 'START <CODE>' where <CODE> is the code from the website.",
                                        )
                                else:
                                    # User is not registered and didn't send START command
                                    await self.send_text(
                                        to=message_from_e164,
                                        text="Welcome! To get started, please visit our website to generate a registration code, then send 'START <CODE>' here.",
                                    )
            return {"status": "processed"}
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            raise e
