from typing import Optional

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.enums import LLMModel, ThesysModel


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database Settings
    database_url: str
    # Pool size for SQLAlchemy connections to the connection pooler
    # With a pooler (40 pool size, 200 max clients), we can use more connections
    # since the pooler multiplexes them. Keep below 200 total client connections.
    db_pool_size: int = 30  # Can be higher with connection pooler (up to ~200 max clients)
    db_max_overflow: int = (
        10  # Additional connections beyond pool_size (total = pool_size + max_overflow)
    )
    db_pool_timeout: int = 30

    # JWT Settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # Cookie Settings
    cookie_name: str = "access_token"
    cookie_secure: bool = Field(
        default=False,
        description="Set to True in production with HTTPS. Required when cookie_samesite='none' for cross-origin requests.",
    )
    cookie_httponly: bool = True
    cookie_samesite: str = Field(
        default="lax",
        description="Cookie SameSite attribute: 'strict', 'lax', or 'none'. Use 'none' for cross-origin requests (requires cookie_secure=True).",
    )

    @field_validator("cookie_samesite")
    @classmethod
    def validate_cookie_samesite(cls, v: str) -> str:
        """Validate cookie_samesite value"""
        valid_values = ["strict", "lax", "none"]
        v_lower = v.lower() if isinstance(v, str) else v
        if v_lower not in valid_values:
            raise ValueError(f"cookie_samesite must be one of {valid_values}, got {v}")
        return v_lower

    @model_validator(mode="after")
    def validate_cookie_secure_with_samesite(self):
        """Ensure Secure=True when SameSite=None (required by browsers)"""
        if self.cookie_samesite.lower() == "none" and not self.cookie_secure:
            raise ValueError(
                "cookie_secure must be True when cookie_samesite='none' "
                "(required by browsers for cross-origin cookies)"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


class LLMSettings(BaseSettings):
    """LLM settings loaded from environment variables"""

    temperature: float = 0
    openai_api_key: str
    orchestrator_model: str = Field(
        default=LLMModel.GPT4oMini.value.get("model"),
        description="Orchestrator model to use",
        validation_alias=AliasChoices("orchestrator_model", "router_model"),
    )
    portfolio_model: str = Field(
        default=LLMModel.GPT4p1.value.get("model"), description="Portfolio model to use"
    )
    web_search_model: str = Field(
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


class SendGridSettings(BaseSettings):
    """SendGrid email service settings loaded from environment variables"""

    api_key: Optional[str] = Field(
        default=None,
        description="SendGrid API key (optional - email service disabled if not set)",
        validation_alias="SENDGRID_API_KEY",
    )
    from_email: Optional[str] = Field(
        default=None,
        description="Default sender email address (must be verified in SendGrid)",
        validation_alias="SENDGRID_FROM_EMAIL",
    )
    from_name: str = Field(
        default="Finto",
        description="Default sender name displayed in email clients",
        validation_alias="SENDGRID_FROM_NAME",
    )

    @property
    def is_configured(self) -> bool:
        """Check if SendGrid is properly configured."""
        return self.api_key is not None and self.from_email is not None

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


settings = Settings()
llm_settings = LLMSettings()
tavily_settings = TavilySettings()
whatsapp_settings = WhatsAppSettings()
pinecone_settings = PineconeSettings()
thesys_settings = ThesysSettings()
sendgrid_settings = SendGridSettings()
