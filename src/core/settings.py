from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.enums import LLMModel, ThesysModel


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database Settings
    database_url: str
    db_pool_size: int = 15
    db_max_overflow: int = 5
    db_pool_timeout: int = 30

    # JWT Settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

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
    router_model: str = Field(
        default=LLMModel.GPT4oMini.value.get("model"), description="Router model to use"
    )
    portfolio_model: str = Field(
        default=LLMModel.GPT4p1.value.get("model"), description="Portfolio model to use"
    )
    news_model: str = Field(
        default=LLMModel.GPT4oMini.value.get("model"), description="News model to use"
    )

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
    wa_verify_token: str = Field(
        default="changeme-verify-token", description="WhatsApp webhook verify token"
    )
    wa_app_secret: Optional[str] = Field(
        default=None, description="WhatsApp app secret for signature verification"
    )
    wa_user_or_system_token: str = Field(
        default="changeme-user-token", description="WhatsApp user or system token"
    )
    wa_phone_number_id: str = Field(
        default="changeme-phone-id", description="WhatsApp phone number ID"
    )
    wa_api_version: str = Field(default="v22.0", description="WhatsApp API version")
    wa_sender_e164: str = Field(
        default="+10000000000",
        description="WhatsApp sender phone number in E.164 format",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


class PineconeSettings(BaseSettings):
    """Pinecone vector database settings loaded from environment variables"""

    index_name: str = Field(
        default="company-symbols-mapping",
        description="Pinecone index name",
        validation_alias="PINECONE_INDEX",
    )
    dimension: int = Field(
        default=1536, description="Vector dimension for OpenAI text-embedding-3-small"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model name",
    )
    api_key: str = Field(..., description="Pinecone API key", validation_alias="PINECONE_API_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Environment variables:
        # PINECONE_INDEX -> index_name
        # PINECONE_API_KEY -> api_key
        # PINECONE_DIMENSION -> dimension (optional, default: 1536 for text-embedding-3-small)
        # PINECONE_EMBEDDING_MODEL -> embedding_model (optional)
    )


class ThesysSettings(BaseSettings):
    thesys_model: str = Field(
        default=ThesysModel.THESYS_GPT_41.value, description="Thesys model to use"
    )
    thesys_enabled: bool = Field(default=False, description="Whether Thesys is enabled")
    thesys_api_key: str = Field(..., description="Thesys API key")
    thesys_base_url: str = Field(..., description="Thesys base URL")
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


settings = Settings()
llm_settings = LLMSettings()
tavily_settings = TavilySettings()
whatsapp_settings = WhatsAppSettings()
pinecone_settings = PineconeSettings()
thesys_settings = ThesysSettings()
