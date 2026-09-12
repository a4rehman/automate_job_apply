import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Job Application Automation Agent"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Security
    SECRET_KEY: str = "super-secret-key-change-in-production-job-agent-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    FERNET_KEY: str = "dGVzdC1rZXktMzItYnl0ZXMtc3RyaW5nLWZvci1mZXJuZXQ="  # Default fallback, override in production
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./job_automation.db"
    
    # Redis / Celery (Optional)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # AI Engine Configuration
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    # Hugging Face configuration
    AI_PROVIDER: str = "openai"  # "openai" or "huggingface"
    HF_API_TOKEN: str = ""
    HF_LLM_MODEL: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    HF_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    HF_INFERENCE_MODE: str = "hosted"  # "hosted" or "self"
    USE_MOCK_AI_FALLBACK: bool = True  # Allows full offline functional test without live LLM API key
    
    # Storage
    UPLOAD_DIR: str = "uploads"
    BROWSER_DATA_DIR: str = "browser_profiles"
    SCREENSHOTS_DIR: str = "uploads/screenshots"
    
    # Automation Defaults
    DEFAULT_MONITOR_INTERVAL_MINUTES: int = 10
    DEFAULT_MIN_MATCH_SCORE: int = 75
    DEFAULT_HIGH_MATCH_THRESHOLD: int = 90
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    
    # Notifications (SMTP / Telegram)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "alerts@jobautomation.local"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("FERNET_KEY", mode="before")
    def ensure_valid_fernet_key(cls, v):
        if not v or v == "dGVzdC1rZXktMzItYnl0ZXMtc3RyaW5nLWZvci1mZXJuZXQ=":
            # Generate a consistent or valid URL-safe base64 32-byte key
            return Fernet.generate_key().decode()
        return v

settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.BROWSER_DATA_DIR, exist_ok=True)
os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
