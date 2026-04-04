from pathlib import Path

from dotenv import load_dotenv

# Load `finto/.env` before any `src.*` imports. `override=True` so values here win over a stray
# `OPENAI_API_KEY` exported in ~/.zprofile, Cursor's inherited env, etc.
_env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_file, override=True)

import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException, Request, status  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

import os  # noqa: E402

from src.api.routes import api_router  # noqa: E402
from src.core.json_logging import logger_for, setup_json_logging  # noqa: E402
from src.core.settings import llm_settings  # noqa: E402

setup_json_logging()
logger = logger_for(__name__)

if os.getenv("FINTO_LOG_OPENAI_KEY_FINGERPRINT", "").lower() in ("1", "true", "yes"):
    k = llm_settings.openai_api_key
    logger.warning(
        "OPENAI_API_KEY fingerprint (prefix + suffix only; revoke key if this log is leaked): "
        "prefix=%s ...%s len=%s",
        k[:14],
        k[-4:] if len(k) > 4 else "****",
        len(k),
    )

app = FastAPI(
    title="Arthik API",
    description="JWT-based authentication API with chat functionality",
    version="0.1.0",
    openapi_tags=[
        {
            "name": "authentication",
            "description": "User authentication operations including register, login, and token management",
        },
        {
            "name": "chat",
            "description": "Chat and conversation endpoints",
        },
        {
            "name": "holdings",
            "description": "Equity holdings management endpoints",
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
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": sanitized_errors,
        },
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
        "https://finto-ui.vercel.app",
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


# Include API router with /api/v1/ prefix
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
