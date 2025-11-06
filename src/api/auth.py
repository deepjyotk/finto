"""Authentication API endpoints - depends ONLY on service layer"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.core.middleware import get_current_user_optional, require_auth
from src.core.settings import settings
from src.deps.providers import get_auth_service
from src.schemas.auth import UserCreate, UserLogin, UserResponse
from src.services.auth_service import AuthService
from src.utils.json_logging import logger_for

logger = logger_for("api.auth")

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account and return the created user information.",
    responses={
        201: {"description": "User successfully created"},
        400: {"description": "Username or email already exists"},
    },
)
async def register(
    user: UserCreate,
    response: Response,
    svc: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Register a new user account.

    Creates a new user in the f_users table with hashed password.

    - **username**: Unique username (required)
    - **email**: Valid email address (required)
    - **full_name**: User's full name (required)
    - **password**: Password with minimum 8 characters (required)

    Returns the created user information.
    """
    logger.info("register_attempt", extra={"username": user.username, "email": user.email})

    # Create user
    created_user = await svc.register(user)

    if not created_user:
        logger.warning("register_failed", extra={"username": user.username})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists",
        )

    # Create access token for the newly registered user
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = svc.create_access_token(
        data={"sub": created_user.username, "user_id": str(created_user.user_id)},
        expires_delta=access_token_expires,
    )

    # Set authentication cookie
    response.set_cookie(
        key=settings.cookie_name,
        value=access_token,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
    )

    logger.info(
        "register_success",
        extra={"username": user.username, "user_id": str(created_user.user_id)},
    )

    return created_user


@router.post(
    "/login",
    response_model=UserResponse,
    summary="Login user",
    description="Authenticate user, set JWT access token cookie, and return user information.",
    responses={
        200: {"description": "Successfully authenticated; JWT token set in cookie"},
        401: {"description": "Invalid username or password"},
    },
)
async def login(
    credentials: UserLogin,
    response: Response,
    svc: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Authenticate user and create session.

    Validates credentials and returns a JWT access token.
    The token is automatically set as an HTTP-only cookie named 'access_token'.

    - **username**: User's username (required)
    - **password**: User's password (required)

    Returns user information and sets authentication cookie.
    """
    logger.info("login_attempt", extra={"username": credentials.username})

    # Authenticate user
    user = await svc.authenticate(credentials.username, credentials.password)

    if not user:
        logger.warning("login_failed", extra={"username": credentials.username})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = svc.create_access_token(
        data={"sub": user.username, "user_id": str(user.user_id)},
        expires_delta=access_token_expires,
    )

    # Set cookie
    response.set_cookie(
        key=settings.cookie_name,
        value=access_token,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
    )

    logger.info(
        "login_success",
        extra={"username": credentials.username, "user_id": str(user.user_id)},
    )

    return UserResponse.model_validate(user)


@router.post(
    "/logout",
    summary="Logout user",
    description="Clear authentication cookie and end user session.",
    responses={
        200: {"description": "Successfully logged out"},
    },
)
async def logout(response: Response):
    """
    Logout user and clear session.

    Removes the authentication cookie, effectively logging out the user.
    No authentication required for this endpoint.

    Returns success message.
    """
    logger.info("logout")

    response.delete_cookie(
        key=settings.cookie_name,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )

    return {"message": "Successfully logged out"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Retrieve information about the currently authenticated user.",
    responses={
        200: {"description": "User information retrieved successfully"},
        401: {"description": "Not authenticated or invalid token"},
    },
)
async def get_current_user(user: dict = Depends(require_auth)):
    """
    Get current authenticated user profile.

    Requires valid JWT token in cookie (access_token).
    Returns user information including user_id, username, email, and full_name.

    **Authentication required**: Yes (JWT token in cookie)
    """
    return UserResponse(
        user_id=user["user_id"],
        username=user["username"],
        email=user["email"],
        full_name=user["full_name"],
    )


@router.get(
    "/verify",
    summary="Verify authentication status",
    description="Check if the current JWT token is valid and return authentication status.",
    responses={
        200: {"description": "Authentication status returned"},
    },
)
async def verify_token(request: Request):
    """
    Verify JWT token validity.

    Checks if there's a valid JWT token in the cookie and returns authentication status.

    Returns:
    - **authenticated**: Boolean indicating if user is authenticated
    - **user_id**: User ID (only if authenticated)
    - **username**: Username (only if authenticated)

    **Authentication required**: No (returns status regardless)
    """
    user = await get_current_user_optional(request)

    if user:
        return {
            "authenticated": True,
            "user_id": user["user_id"],
            "username": user["username"],
        }
    else:
        return {"authenticated": False}
