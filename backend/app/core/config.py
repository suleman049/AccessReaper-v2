from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "accessreaper_v2.db"


class Settings(BaseSettings):
    PROJECT_NAME: str = "AccessReaper v2"
    VERSION: str = "2.0.0"
    ENV: str = "dev"
    HOST: str = "127.0.0.1"
    PORT: int = 8100

    # Auth configuration
    AUTH_MODE: str = "firebase"  # "firebase" or "dev"
    FIREBASE_PROJECT_ID: str = "accessreaper"
    FIRESTORE_DATABASE_ID: str = "accessreaper-profiles"
    ORGANIZATION_ID: str = "acme"

    # Firebase Admin SDK service account key path
    FIREBASE_SERVICE_ACCOUNT_PATH: str = str((BASE_DIR / "secrets" / "firebase-service-account.json").resolve())

    # Database
    DATABASE_URL: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

    # DRY_RUN guard: must always be True in Phase 1
    DRY_RUN: bool = True
    ALLOW_MANUAL_AUDIT: bool = False

    # Rate limiting (requests per minute for mutating actions)
    MUTATING_RATE_LIMIT_PER_MINUTE: int = 60

    # Paths
    FRONTEND_DIR: str = str((BASE_DIR.parent / "frontend").resolve())

    # Phase 3: Encryption & GitHub integration
    APP_ENCRYPTION_KEY: str = "V4oAd0dJDtuj3gKTTjwCk4zBXkxQ0l3wOva6eNCDGtk="
    GITHUB_TOKEN: str | None = None
    GITHUB_API_BASE: str = "https://api.github.com"
    GITHUB_MAX_SYNC_REQUESTS: int = 2000
    ENABLE_LIVE_GITHUB_REVOCATION: bool = True

    # LLM Explanations (Groq primary, Gemini fallback, Generic OpenAI)
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = ""
    LLM_PROVIDER_ORDER: str = "groq,gemini"
    LLM_DAILY_TOKEN_BUDGET: int = 200000
    LLM_MAX_FINDINGS_PER_CALL: int = 6
    LLM_SEND_REAL_NAMES: bool = False

    # Generic OpenAI-compatible fallback / alternative
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = ""

    # Legacy / Optional Gemini Settings
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = ""
    GEMINI_SEND_REAL_NAMES: bool = False
    GEMINI_MAX_CALLS_PER_RUN: int = 50

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "notifications@accessreaper.local"
    SMTP_FROM_NAME: str = "AccessReaper"
    PUBLIC_BASE_URL: str = "http://localhost:8100"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
