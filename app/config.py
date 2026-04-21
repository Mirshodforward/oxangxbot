from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Any, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Bot settings
    BOT_TOKEN: str
    
    # FastSaverAPI settings
    TOKEN: str  # API token for FastSaverAPI
    API_BASE_URL: str = "https://api.fastsaver.io/v1"

    @field_validator("API_BASE_URL", mode="before")
    @classmethod
    def normalize_api_base_url(cls, v: Any) -> str:
        """Eski .env va /v1 siz hostlarni yangi API ga moslashtirish."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "https://api.fastsaver.io/v1"
        u = str(v).strip().rstrip("/")
        low = u.lower()
        if "fastsaverapi.com" in low:
            return "https://api.fastsaver.io/v1"
        if "api.fastsaver.io" in low and "/v1" not in low:
            return f"{u}/v1"
        return u
    
    # Database settings
    DATABASE_URL: str
    
    # Bot info
    BOT_USERNAME: Optional[str] = None
    
    # Admin settings (comma-separated string)
    ADMIN_IDS_STR: str = ""
    
    @property
    def ADMIN_IDS(self) -> list[int]:
        """Parse comma-separated admin IDs"""
        if not self.ADMIN_IDS_STR.strip():
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS_STR.split(',') if x.strip()]
    
    # Mock mode for testing (when API is unavailable)
    MOCK_MODE: bool = False
    
    # Gemini API for voice recognition
    GEMINI_API_KEY: Optional[str] = None

    # Instagram CDN: ko‘p serverlar 403 beradi — rezident proxy (HTTPS_PROXY) tavsiya etiladi
    HTTP_PROXY: Optional[str] = None
    HTTPS_PROXY: Optional[str] = None

    # Faqat instagram.com/reel/... — eski get-info API (TOKEN_REELS, alohida host)
    API_BASE_URL_REELS: Optional[str] = None
    TOKEN_REELS: Optional[str] = None

    @field_validator("API_BASE_URL_REELS", mode="before")
    @classmethod
    def reels_base_url(cls, v: Any) -> Optional[str]:
        if v is None or not str(v).strip():
            return None
        return str(v).strip().rstrip("/")

    @field_validator("TOKEN_REELS", mode="before")
    @classmethod
    def reels_token(cls, v: Any) -> Optional[str]:
        if v is None or not str(v).strip():
            return None
        return str(v).strip()


settings = Settings()
