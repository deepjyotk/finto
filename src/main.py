import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.auth import router as auth_router
from src.api.chat import router as chat_router
from src.api.holdings import router as holdings_router
from src.api.home import router as home_router
from src.api.kiteconnect_integration import router as kite_router
from src.api.whatsapp import router as whatsapp_router
from src.core.json_logging import logger_for, setup_json_logging

load_dotenv()

setup_json_logging()
logger = logger_for(__name__)

app = FastAPI(
    title="Finto API",
    description="JWT-based authentication API with chat functionality",
    version="0.1.0",
    openapi_tags=[
        {
            "name": "authentication",
            "description": "User authentication operations including register, login, and \
            token management",
        },
        {
            "name": "chat",
            "description": "Chat and conversation endpoints",
        },
        {
            "name": "holdings",
            "description": "Equity holdings management endpoints",
        },
        {
            "name": "home",
            "description": "Home feed endpoints for user integrations",
        },
    ],
)


def _sanitize_errors(errors: list) -> list:
    """Convert non-serializable values (like bytes) in error dicts to strings."""
    sanitized = []
    for error in errors:
        sanitized_error = {}
        for key, value in error.items():
            if isinstance(value, bytes):
                # Try to decode as UTF-8, fallback to repr if it fails
                try:
                    sanitized_error[key] = value.decode("utf-8")
                except UnicodeDecodeError:
                    sanitized_error[key] = f"<bytes: {len(value)} bytes>"
            elif isinstance(value, (dict, list)):
                sanitized_error[key] = (
                    _sanitize_errors(value)
                    if isinstance(value, list)
                    else {
                        k: (v.decode("utf-8") if isinstance(v, bytes) else v)
                        for k, v in value.items()
                    }
                )
            else:
                sanitized_error[key] = value
        sanitized.append(sanitized_error)
    return sanitized


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    sanitized_errors = _sanitize_errors(errors)
    logger.error(
        "validation_error",
        extra={"path": request.url.path, "method": request.method, "errors": sanitized_errors},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": sanitized_errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "type": type(exc).__name__,
        },
    )
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://finto-lry24myhi-deepjyot-kapoors-projects.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/healthz", tags=["health"])
async def health_check():
    """Health check endpoint for container orchestration"""
    return {"status": "healthy", "service": "finto-api"}


# Include routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(holdings_router)
app.include_router(home_router)
app.include_router(kite_router)
app.include_router(whatsapp_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
