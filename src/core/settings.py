from typing import List, Literal, Optional

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
    tavily_finance_whitelist: str = Field(
        default="nseindia.com,bseindia.com,sebi.gov.in,rbi.org.in,mca.gov.in",
        description="Tavily finance whitelist",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


class WhatsAppSettings(BaseSettings):
    wa_verify_token: str = Field(..., description="WhatsApp webhook verify token")
    wa_app_secret: Optional[str] = Field(None, description="WhatsApp app secret for signature verification")
    wa_user_or_system_token: str = Field(..., description="WhatsApp user or system token")
    wa_phone_number_id: str = Field(..., description="WhatsApp phone number ID")
    wa_api_version: str = Field(default="v22.0", description="WhatsApp API version")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


settings = Settings()
llm_settings = LLMSettings()
tavily_settings = TavilySettings()
whatsapp_settings = WhatsAppSettings()
