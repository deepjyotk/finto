"""Centralized route registration with /api/v1/ prefix"""

from fastapi import APIRouter

from src.api.auth import router as auth_router
from src.api.chat import router as chat_router
from src.api.holdings import router as holdings_router
from src.api.kiteconnect_integration import router as kite_router
from src.api.thesys_chat import router as thesys_chat_router
from src.api.whatsapp import router as whatsapp_router

# Create main API router with /api/v1/ prefix
api_router = APIRouter(prefix="/api/v1")

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(holdings_router)
api_router.include_router(kite_router)
api_router.include_router(thesys_chat_router)
api_router.include_router(whatsapp_router)
