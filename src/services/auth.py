"""Authentication service - pure class for business logic, no FastAPI imports"""

import asyncio
import random
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import jwt
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from passlib.context import CryptContext

from src.api.schemas.auth import TokenData, UserCreate, UserResponse
from src.core.json_logging import logger_for
from src.models.user import User
from src.repositories.pending_registration_repo import PendingRegistrationRepository
from src.repositories.user_repo import UserRepository
from src.services.email import EmailService

logger = logger_for(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# OTP expiry in minutes
OTP_EXPIRY_MINUTES = 5
# Minimum time between OTP resend requests in seconds
OTP_RESEND_COOLDOWN_SECONDS = 60
# Maximum OTP verification attempts
MAX_OTP_ATTEMPTS = 5


class AuthService:
    """Service layer for authentication operations"""

    def __init__(
        self,
        repo: UserRepository,
        pending_repo: PendingRegistrationRepository,
        secret_key: str,
        algorithm: str = "HS256",
        email_service: Optional[EmailService] = None,
    ):
        """
        Initialize AuthService.

        Args:
            repo: UserRepository instance for data access
            pending_repo: PendingRegistrationRepository for OTP-based registration
            secret_key: Secret key for JWT encoding
            algorithm: Algorithm for JWT encoding (default: HS256)
            email_service: EmailService for sending OTP emails (optional for testing)
        """
        self.repo = repo
        self.pending_repo = pending_repo
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.email_service = email_service

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    @staticmethod
    def generate_otp() -> str:
        """Generate a 6-digit OTP."""
        return "".join([str(secrets.randbelow(10)) for _ in range(6)])

    @staticmethod
    def hash_otp(otp: str) -> str:
        """Hash OTP with salt using the same password context."""
        return pwd_context.hash(otp)

    @staticmethod
    def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
        """Verify a plain OTP against a hashed OTP."""
        return pwd_context.verify(plain_otp, hashed_otp)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.

        Args:
            data: Data to encode in the token
            expires_delta: Token expiration time (optional)

        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=30)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[TokenData]:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            TokenData if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            user_id: str = payload.get("user_id")
            if username is None:
                return None
            return TokenData(username=username, user_id=user_id)
        except jwt.PyJWTError:
            return None

    async def initiate_registration(self, user_data: UserCreate) -> tuple[bool, str, Optional[str]]:
        """
        Initiate registration by creating pending registration and sending OTP.

        Args:
            user_data: User registration data

        Returns:
            Tuple of (success, message, otp_for_testing)
            - otp_for_testing is only returned for mocked email sending
        """
        # Check if user already exists in f_users
        existing_user = await self.repo.by_username(user_data.username)
        if existing_user:
            return False, "Username already exists", None

        existing_email = await self.repo.by_email(user_data.email)
        if existing_email:
            return False, "Email already exists", None

        # Check for existing pending registration
        existing_pending = await self.pending_repo.by_email(user_data.email)
        now = datetime.now(timezone.utc)

        if existing_pending:
            # Check if attempts exceeded
            if existing_pending.attempts >= MAX_OTP_ATTEMPTS:
                return False, "Too many OTP attempts. Please try again later.", None

            # Check cooldown period (must wait at least 1 minute between resends)
            time_since_created = (now - existing_pending.created_at).total_seconds()
            if time_since_created < OTP_RESEND_COOLDOWN_SECONDS:
                remaining = int(OTP_RESEND_COOLDOWN_SECONDS - time_since_created)
                return (
                    False,
                    f"Please wait {remaining} seconds before requesting a new OTP",
                    None,
                )

            # Delete old pending registration to create a new one
            await self.pending_repo.delete_by_email(user_data.email)

        # Generate OTP and hash it
        otp = self.generate_otp()
        otp_hash = self.hash_otp(otp)
        password_hash = self.get_password_hash(user_data.password)

        # Create pending registration
        expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
        await self.pending_repo.add(
            id=uuid4(),
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            password_hash=password_hash,
            otp_hash=otp_hash,
            expires_at=expires_at,
        )

        # Commit at the use-case boundary
        await self.pending_repo.session.commit()

        # Send OTP email
        if self.email_service:
            success, error_msg = await self.email_service.send_otp_email(
                to_email=user_data.email,
                otp=otp,
                username=user_data.username,
            )
            if not success:
                # Log error but don't fail registration - OTP is already stored
                # User can request a new OTP if email fails
                logger.error(
                    "otp_email_send_failed",
                    extra={"email": user_data.email, "error": error_msg},
                )
                return (
                    False,
                    f"Failed to send OTP email. Please try again. Error: {error_msg}",
                    None,
                )
            logger.info(
                "otp_email_sent_successfully",
                extra={"email": user_data.email, "username": user_data.username},
            )
        else:
            # Fallback for testing without email service
            logger.warning("email_service_not_configured", extra={"email": user_data.email})
            await asyncio.sleep(1)  # Minimal delay for testing

        # Return success (OTP not returned in production)
        return True, "OTP sent successfully", None

    async def verify_otp_and_create_user(
        self, email: str, otp: str
    ) -> tuple[bool, str, Optional[UserResponse]]:
        """
        Verify OTP and create the user if valid.

        Args:
            email: User's email
            otp: OTP provided by user

        Returns:
            Tuple of (success, message, user_response)
        """
        pending = await self.pending_repo.by_email(email)

        if not pending:
            return False, "No pending registration found for this email", None

        now = datetime.now(timezone.utc)

        # Check if OTP expired
        if pending.expires_at < now:
            return False, "OTP has expired. Please register again.", None

        # Check if attempts exceeded
        if pending.attempts >= MAX_OTP_ATTEMPTS:
            return False, "Too many failed attempts. Please register again.", None

        # Verify OTP
        if not self.verify_otp(otp, pending.otp_hash):
            # Increment attempts
            await self.pending_repo.increment_attempts(pending)
            await self.pending_repo.session.commit()
            remaining = MAX_OTP_ATTEMPTS - pending.attempts - 1
            return False, f"Invalid OTP. {remaining} attempts remaining.", None

        # OTP is valid - create the user
        # First check again that username/email don't exist (race condition protection)
        existing_user = await self.repo.by_username(pending.username)
        if existing_user:
            await self.pending_repo.delete_by_email(email)
            await self.pending_repo.session.commit()
            return (
                False,
                "Username was taken while verifying. Please register again.",
                None,
            )

        existing_email = await self.repo.by_email(pending.email)
        if existing_email:
            await self.pending_repo.delete_by_email(email)
            await self.pending_repo.session.commit()
            return (
                False,
                "Email was registered while verifying. Please try again.",
                None,
            )

        # Create the user
        user = await self.repo.add(
            user_id=uuid4(),
            username=pending.username,
            email=pending.email,
            full_name=pending.full_name,
            password_hash=pending.password_hash,
        )

        # Delete pending registration
        await self.pending_repo.delete_by_email(email)

        # Commit everything
        await self.repo.session.commit()

        return (
            True,
            "Registration successful",
            UserResponse(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
            ),
        )

    async def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise
        """
        user = await self.repo.by_username(username)
        if not user:
            return None
        if user.password_hash is None:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def derive_base_username_from_email(email: str) -> str:
        """Build a username base from the local part of an email (alphanumeric only)."""
        local = email.split("@", 1)[0].lower()
        base = re.sub(r"[^a-z0-9]", "", local)
        if not base:
            base = "user"
        return base[:50]

    async def _allocate_unique_username(self, base: str) -> str:
        """Pick a username: try `base`, then `base_NNNN` until unique."""
        candidate = base
        for _ in range(200):
            existing = await self.repo.by_username(candidate)
            if not existing:
                return candidate
            candidate = f"{base}_{random.randint(1000, 9999)}"
        return f"{base}_{uuid4().hex[:8]}"

    async def google_oauth_login(
        self, credential: str, google_client_id: str
    ) -> tuple[bool, str, Optional[User]]:
        """
        Verify a Google ID token, then find or create a user in f_users.

        Returns:
            (success, message, user) — user is set only when success is True.
        """
        if not google_client_id or not str(google_client_id).strip():
            return False, "Google Sign-In is not configured", None

        try:
            idinfo = google_id_token.verify_oauth2_token(
                credential,
                google_auth_requests.Request(),
                google_client_id,
            )
        except ValueError:
            logger.warning("google_oauth_token_invalid")
            return False, "Invalid Google credential", None

        if not idinfo.get("email_verified", False):
            return False, "Google email is not verified", None

        google_sub = idinfo.get("sub")
        email = idinfo.get("email")
        name = idinfo.get("name") or (email.split("@")[0] if email else "User")

        if not google_sub or not email:
            return False, "Google token missing required claims", None

        user = await self.repo.by_google_id(google_sub)
        if user:
            return True, "ok", user

        existing = await self.repo.by_email(email)
        if existing:
            if existing.google_id is not None and existing.google_id != google_sub:
                return False, "This email is linked to another Google account", None
            existing.google_id = google_sub
            existing.auth_provider = "google"
            await self.repo.session.flush()
            await self.repo.session.commit()
            return True, "ok", existing

        base_username = self.derive_base_username_from_email(email)
        username = await self._allocate_unique_username(base_username)
        user = await self.repo.add(
            user_id=uuid4(),
            username=username,
            email=email,
            full_name=name,
            password_hash=None,
            google_id=google_sub,
            auth_provider="google",
        )
        await self.repo.session.commit()
        return True, "ok", user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: Username to search for

        Returns:
            User object if found, None otherwise
        """
        return await self.repo.by_username(username)
