"""Authentication middleware using clean architecture"""
from typing import Optional, Annotated

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer

from src.core.settings import settings
from src.services.auth_service import AuthService
from src.deps.providers import get_auth_service
from src.schemas.auth import TokenData


security = HTTPBearer(auto_error=False)


async def get_current_user_from_cookie(
    request: Request,
    svc: Annotated[AuthService, Depends(get_auth_service)]
) -> Optional[dict]:
    """
    Middleware function to authenticate user from cookie.
    Extracts JWT token from cookie and validates it.
    
    Args:
        request: FastAPI request object
        svc: AuthService instance (injected)
        
    Returns:
        User dict if authenticated, None otherwise
    """
    token = request.cookies.get(settings.cookie_name)
    
    if not token:
        return None
    
    # Verify token
    token_data: Optional[TokenData] = svc.verify_token(token)
    if not token_data or not token_data.username:
        return None
    
    # Get user from database
    user = await svc.get_user_by_username(token_data.username)
    if not user:
        return None
    
    # Return user as dict for backward compatibility with existing endpoints
    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name
    }


async def require_auth(
    request: Request,
    svc: Annotated[AuthService, Depends(get_auth_service)]
) -> dict:
    """
    Dependency that requires authentication.
    Raises HTTPException if user is not authenticated.
    
    Args:
        request: FastAPI request object
        svc: AuthService instance (injected)
        
    Returns:
        User dict if authenticated
        
    Raises:
        HTTPException: If not authenticated
    """
    user = await get_current_user_from_cookie(request, svc)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_optional(
    request: Request,
    svc: Annotated[AuthService, Depends(get_auth_service)]
) -> Optional[dict]:
    """
    Optional authentication - returns user if authenticated, None otherwise.
    Does not raise exception if not authenticated.
    
    Args:
        request: FastAPI request object
        svc: AuthService instance (injected)
        
    Returns:
        User dict if authenticated, None otherwise
    """
    return await get_current_user_from_cookie(request, svc)
