import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import router as auth_router
from src.api.chat import router as chat_router
from src.utils.json_logging import setup_json_logging

setup_json_logging()

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
    ],
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(chat_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
