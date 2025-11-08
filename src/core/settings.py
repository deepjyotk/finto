from typing import List, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database Settings
    database_url: str

    # JWT Settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Cookie Settings
    cookie_name: str = "access_token"
    cookie_secure: bool = False  # Set to True in production with HTTPS
    cookie_httponly: bool = True
    cookie_samesite: str = "lax"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


class LLMSettings(BaseSettings):
    """LLM settings loaded from environment variables"""

    temperature: float = 0
    openai_api_key: str
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


class TavilySettings(BaseSettings):
    tavily_api_key: str = Field(default=..., description="Tavily API key")
    tavily_finance_whitelist: str = Field(default="nseindia.com,bseindia.com,sebi.gov.in,rbi.org.in,mca.gov.in", description="Tavily finance whitelist")

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }

settings = Settings()
llm_settings = LLMSettings()
tavily_settings = TavilySettings()
settings = Settings()
