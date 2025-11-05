from typing import Optional

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.core.config import settings
from src.services.auth_service import auth_service
from src.schemas.auth import TokenData


security = HTTPBearer(auto_error=False)


async def get_current_user_from_cookie(request: Request) -> Optional[dict]:
    """
    Middleware function to authenticate user from cookie.
    Extracts JWT token from cookie and validates it.
    """
    token = request.cookies.get(settings.COOKIE_NAME)
    
    if not token:
        return None
    
    # Verify token
    token_data: Optional[TokenData] = auth_service.verify_token(token)
    if not token_data or not token_data.username:
        return None
    
    # Get user from database
    user = await auth_service.get_user_by_username(token_data.username)
    if not user:
        return None
    
    return user


async def require_auth(request: Request) -> dict:
    """
    Dependency that requires authentication.
    Raises HTTPException if user is not authenticated.
    """
    user = await get_current_user_from_cookie(request)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_optional(request: Request) -> Optional[dict]:
    """
    Optional authentication - returns user if authenticated, None otherwise.
    Does not raise exception if not authenticated.
    """
    return await get_current_user_from_cookie(request)

