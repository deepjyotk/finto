from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import jwt
from passlib.context import CryptContext
from supabase import create_client, Client

from src.core.config import settings
from src.schemas.auth import UserCreate, UserResponse, TokenData

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service layer for authentication operations"""
    
    def __init__(self):
        self.supabase: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username: str = payload.get("sub")
            user_id: str = payload.get("user_id")
            if username is None:
                return None
            return TokenData(username=username, user_id=user_id)
        except jwt.PyJWTError:
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """Get user from Supabase by username"""
        try:
            response = self.supabase.table("f_users").select("*").eq("username", username).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception:
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user from Supabase by email"""
        try:
            response = self.supabase.table("f_users").select("*").eq("email", email).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception:
            return None
    
    async def create_user(self, user: UserCreate) -> Optional[UserResponse]:
        """Create a new user in Supabase"""
        try:
            # Check if user already exists
            existing_user = await self.get_user_by_username(user.username)
            if existing_user:
                return None
            
            existing_email = await self.get_user_by_email(user.email)
            if existing_email:
                return None
            
            # Hash password
            hashed_password = self.get_password_hash(user.password)
            
            # Create user data
            user_data = {
                "user_id": str(uuid4()),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "password_hash": hashed_password
            }
            
            # Insert into Supabase
            response = self.supabase.table("f_users").insert(user_data).execute()
            
            if response.data and len(response.data) > 0:
                created_user = response.data[0]
                return UserResponse(
                    user_id=created_user["user_id"],
                    username=created_user["username"],
                    email=created_user["email"],
                    full_name=created_user["full_name"]
                )
            return None
        except Exception:
            return None
    
    async def authenticate_user(self, username: str, password: str) -> Optional[dict]:
        """Authenticate user with username and password"""
        user = await self.get_user_by_username(username)
        if not user:
            return None
        if not self.verify_password(password, user.get("password_hash", "")):
            return None
        return user


auth_service = AuthService()

