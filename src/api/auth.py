"""Authentication API endpoints - depends ONLY on service layer"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.schemas.auth import (
    OTPResponse,
    OTPVerifyRequest,
    UserCreate,
    UserLogin,
    UserResponse,
)
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.core.settings import settings
from src.dependencies import get_auth_service
from src.services.auth import AuthService

logger = logger_for(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=OTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Register a new user (initiates OTP verification)",
    description="Initiate registration by sending an OTP to the user's email. Use /verify-otp to complete registration.",
    responses={
        200: {"description": "OTP sent successfully"},
        400: {"description": "Username or email already exists, or rate limited"},
    },
)
async def register(
    user: UserCreate,
    svc: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Initiate user registration with OTP verification.

    Creates a pending registration and sends an OTP to the user's email.
    The user must verify the OTP using /verify-otp to complete registration.
    This endpoint can also be used to resend OTP (with 1-minute cooldown).

    - **username**: Unique username (required)
    - **email**: Valid email address (required)
    - **full_name**: User's full name (required)
    - **password**: Password with minimum 8 characters (required)

    Returns success message when OTP is sent.
    """
    logger.info(
        "register_attempt", extra={"username": user.username, "email": user.email}
    )

    success, message, _ = await svc.initiate_registration(user)

    if not success:
        logger.error(
            "register_failed", extra={"username": user.username, "reason": message}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    logger.info(
        "register_otp_sent", extra={"username": user.username, "email": user.email}
    )

    return OTPResponse(message=message)


@router.post(
    "/verify-otp",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Verify OTP and complete registration",
    description="Verify the OTP sent to the user's email and create the user account.",
    responses={
        201: {"description": "User successfully created"},
        400: {"description": "Invalid or expired OTP"},
    },
)
async def verify_otp(
    otp_data: OTPVerifyRequest,
    response: Response,
    svc: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Verify OTP and complete user registration.

    Validates the OTP and creates the user account if valid.
    Sets authentication cookie on success.

    - **email**: Email used during registration (required)
    - **otp**: 6-digit OTP received via email (required)

    Returns the created user information.
    """
    logger.info("verify_otp_attempt", extra={"email": otp_data.email})

    success, message, created_user = await svc.verify_otp_and_create_user(
        email=otp_data.email, otp=otp_data.otp
    )

    if not success or not created_user:
        logger.error(
            "verify_otp_failed", extra={"email": otp_data.email, "reason": message}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
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
        "verify_otp_success",
        extra={"email": otp_data.email, "user_id": str(created_user.user_id)},
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
