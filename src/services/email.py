"""Email service - SendGrid integration for sending emails"""

from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from src.core.json_logging import logger_for

logger = logger_for(__name__)


class EmailService:
    """Service layer for email operations using SendGrid"""

    def __init__(self, api_key: Optional[str], from_email: Optional[str], from_name: str):
        """
        Initialize EmailService.

        Args:
            api_key: SendGrid API key (can be None to disable email sending)
            from_email: Default sender email address (can be None to disable email sending)
            from_name: Default sender name
        """
        if api_key is None or from_email is None:
            logger.warning(
                "email_service_disabled",
                extra={"reason": "SendGrid API key or from_email not configured"},
            )
            self.client = None
            self.from_email = None
            self.from_name = from_name
        else:
            self.client = SendGridAPIClient(api_key)
            self.from_email = from_email
            self.from_name = from_name

    async def send_otp_email(
        self, to_email: str, otp: str, username: str
    ) -> tuple[bool, Optional[str]]:
        """
        Send OTP email to user.

        Args:
            to_email: Recipient email address
            otp: 6-digit OTP code
            username: User's username

        Returns:
            Tuple of (success, error_message)
        """
        subject = "Your Arthik Registration OTP"
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">Welcome to Arthik!</h2>
                <p>Hi {username},</p>
                <p>Thank you for registering with Arthik. Please use the following OTP to complete your registration:</p>
                <div style="background-color: #f3f4f6; border: 2px solid #2563eb; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                    <h1 style="color: #2563eb; font-size: 32px; letter-spacing: 4px; margin: 0;">{otp}</h1>
                </div>
                <p>This OTP will expire in 5 minutes.</p>
                <p>If you didn't request this registration, please ignore this email.</p>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                <p style="color: #6b7280; font-size: 12px;">This is an automated message, please do not reply.</p>
            </div>
        </body>
        </html>
        """
        plain_text_content = f"""
        Welcome to Arthik!

        Hi {username},

        Thank you for registering with Arthik. Please use the following OTP to complete your registration:

        {otp}

        This OTP will expire in 5 minutes.

        If you didn't request this registration, please ignore this email.

        ---
        This is an automated message, please do not reply.
        """

        return await self._send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            plain_text_content=plain_text_content,
        )

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_text_content: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Send email using SendGrid.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            plain_text_content: Plain text email body

        Returns:
            Tuple of (success, error_message)
        """
        if self.client is None or self.from_email is None:
            return (
                False,
                "Email service is not configured. Please set SENDGRID_API_KEY and SENDGRID_FROM_EMAIL environment variables.",
            )

        try:
            message = Mail(
                from_email=(self.from_email, self.from_name),
                to_emails=to_email,
                subject=subject,
                html_content=html_content,
                plain_text_content=plain_text_content,
            )

            # SendGrid SDK is synchronous, so we run it in a thread pool
            # to avoid blocking the async event loop
            import asyncio
            from functools import partial

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, partial(self.client.send, message))

            if response.status_code in [200, 201, 202]:
                logger.info(
                    "email_sent_successfully",
                    extra={
                        "to": to_email,
                        "subject": subject,
                        "status_code": response.status_code,
                    },
                )
                return True, None
            else:
                error_msg = f"SendGrid returned status code {response.status_code}: {response.body}"
                logger.error(
                    "email_send_failed",
                    extra={"to": to_email, "subject": subject, "error": error_msg},
                )
                return False, error_msg

        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error messages for common SendGrid errors
            if "403" in error_msg or "Forbidden" in error_msg:
                detailed_error = (
                    "SendGrid returned 403 Forbidden. This usually means:\n"
                    "1. The sender email address is not verified in SendGrid\n"
                    "2. The API key doesn't have 'Mail Send' permissions\n"
                    "3. The API key is invalid or expired\n\n"
                    "Please verify your sender email in SendGrid Dashboard → Settings → Sender Authentication"
                )
            elif "401" in error_msg or "Unauthorized" in error_msg:
                detailed_error = (
                    "SendGrid API key is invalid or expired. Please check your SENDGRID_API_KEY."
                )
            else:
                detailed_error = error_msg

            logger.error(
                "email_send_exception",
                extra={"to": to_email, "subject": subject, "error": error_msg},
                exc_info=True,
            )
            return False, detailed_error
