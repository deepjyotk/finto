"""Authentication service - pure class for business logic, no FastAPI imports"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import jwt
from passlib.context import CryptContext

from src.models.user import User
from src.repositories.user_repo import UserRepository
from src.schemas.auth import TokenData, UserCreate, UserResponse

# Password hashing context
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class AuthService:
    """Service layer for authentication operations"""

    def __init__(self, repo: UserRepository, secret_key: str, algorithm: str = "HS256"):
        """
        Initialize AuthService.

        Args:
            repo: UserRepository instance for data access
            secret_key: Secret key for JWT encoding
            algorithm: Algorithm for JWT encoding (default: HS256)
        """
        self.repo = repo
        self.secret_key = secret_key
        self.algorithm = algorithm

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

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

    async def register(self, user_data: UserCreate) -> Optional[UserResponse]:
        """
        Register a new user.

        This is the use-case boundary - handles the full registration transaction.

        Args:
            user_data: User registration data

        Returns:
            UserResponse if successful, None if username/email already exists
        """
        # Check if user already exists
        existing_user = await self.repo.by_username(user_data.username)
        if existing_user:
            return None

        existing_email = await self.repo.by_email(user_data.email)
        if existing_email:
            return None

        # Hash password
        password_hash = self.get_password_hash(user_data.password)

        # Create user
        user = await self.repo.add(
            user_id=uuid4(),
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            password_hash=password_hash,
        )

        # Commit at the use-case boundary
        await self.repo.session.commit()

        return UserResponse(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
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
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: Username to search for

        Returns:
            User object if found, None otherwise
        """
        return await self.repo.by_username(username)
