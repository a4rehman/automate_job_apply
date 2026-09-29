import os
import secrets
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
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "insecure-dev-secret-key-job-agent-change-in-prod")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    FERNET_KEY: str = ""  # Generated dynamically if not provided in env
    
    # Database (TiDB Cloud / SQLite fallback)
    DATABASE_URL: str = "sqlite+aiosqlite:///./job_automation.db"
    TIDB_HOST: str = ""
    TIDB_PORT: int = 4000
    TIDB_USER: str = ""
    TIDB_PASSWORD: str = ""
    TIDB_DATABASE: str = "job_automation"
    TIDB_CA_PATH: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 300
    # Postgres/Supabase TLS posture: "require" | "verify-full" | "disable".
    # Supabase rejects non-TLS connections, so require is the sane default.
    DB_SSL_MODE: str = "require"
    
    # Redis / Celery (Optional)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Google Gemini AI Decision Engine
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"
    GEMINI_TEMPERATURE: float = 0.1
    
    # Legacy / Alternative AI Engine Configuration
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    # Hugging Face configuration
    AI_PROVIDER: str = "gemini"  # "gemini", "openai", or "huggingface"
    HF_API_TOKEN: str = ""
    HF_LLM_MODEL: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    HF_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    HF_INFERENCE_MODE: str = "hosted"  # "hosted" or "self"
    USE_MOCK_AI_FALLBACK: bool = True  # Allows full offline functional test without live LLM API key
    
    # Decision Engine Thresholds (Scores between 0.0 and 1.0)
    HIGH_MATCH_THRESHOLD: float = 0.85
    REVIEW_THRESHOLD: float = 0.70
    MIN_CONFIDENCE: float = 0.60
    
    # Streamlit Auth & App Security
    APP_PASSWORD_HASH: str = ""  # bcrypt / argon2 hash for secure login gate
    
    # Storage
    UPLOAD_DIR: str = "uploads"
    BROWSER_DATA_DIR: str = "browser_profiles"
    SCREENSHOTS_DIR: str = "uploads/screenshots"
    
    # Automation Modes
    AUTOMATION_MODE: str = "SAFE_MODE"  # SAFE_MODE, ASSISTED_MODE, AUTHORIZED_AUTO_MODE
    DEFAULT_MONITOR_INTERVAL_MINUTES: int = 10
    DEFAULT_MIN_MATCH_SCORE: int = 75
    DEFAULT_HIGH_MATCH_THRESHOLD: int = 90
    
    # Daily Safety Limits
    MAX_APPLICATIONS_PER_DAY: int = 30
    MAX_APPLICATIONS_PER_RUN: int = 10
    MIN_MATCH_SCORE: int = 85
    COOLDOWN_SECONDS: int = 3600
    MAX_RETRIES: int = 3
    
    # Seed Control
    SEED_DEMO_DATA: bool = False
    
    # Automation
    AUTOMATION_TIMEZONE: str = "Asia/Karachi"
    DRY_RUN: bool = True
    # Hard master switch for unattended submissions. Even when False, every
    # application must additionally be in a READY_TO_SUBMIT/approved state and
    # pass the human-approval rules. Default stays False.
    AUTO_SUBMIT_ENABLED: bool = False
    # When True, no cycle may ever submit: it can only prepare + request review.
    REQUIRE_HUMAN_APPROVAL: bool = True
    
    # Scheduler
    SCHEDULER_LOCK_TIMEOUT_SECONDS: int = 3600
    
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
    NOTIFICATION_EMAIL_TO: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("SECRET_KEY", mode="before")
    def validate_secret_key(cls, v, info):
        insecure_defaults = {
            "super-secret-key-change-in-production-job-agent-2026",
            "insecure-dev-secret-key-job-agent-change-in-prod",
            "secret",
            "",
        }
        if v in insecure_defaults:
            return secrets.token_urlsafe(48)
        return v

    @field_validator("FERNET_KEY", mode="before")
    def ensure_valid_fernet_key(cls, v):
        if not v or v == "dGVzdC1rZXktMzItYnl0ZXMtc3RyaW5nLWZvci1mZXJuZXQ=":
            return Fernet.generate_key().decode()
        return v

settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.BROWSER_DATA_DIR, exist_ok=True)
os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
