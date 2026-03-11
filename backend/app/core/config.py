from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # App
    APP_NAME: str = "DocVault"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://docvault:docvault_dev@postgres:5432/docvault"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://docvault:docvault_dev@postgres:5432/docvault"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # ── LLM Provider Switch ──────────────────────────────────────
    # "anthropic" | "google" | "openai"
    LLM_PROVIDER: str = "google"

    # ── API Keys (only the active provider's key is required) ───
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # ── Model names per provider ────────────────────────────────
    # Anthropic
    ANTHROPIC_PRIMARY_MODEL: str = "claude-sonnet-4-20250514"
    ANTHROPIC_FAST_MODEL: str = "claude-haiku-4-20250414"
    # Google Gemini
    GOOGLE_PRIMARY_MODEL: str = "gemini-2.5-flash"
    GOOGLE_FAST_MODEL: str = "gemini-2.5-flash"
    # OpenAI
    OPENAI_PRIMARY_MODEL: str = "gpt-4o"
    OPENAI_FAST_MODEL: str = "gpt-4o-mini"

    # ── Embedding ───────────────────────────────────────────────
    # "openai" | "google"
    EMBEDDING_PROVIDER: str = "google"
    # OpenAI embedding
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536
    # Google embedding
    GOOGLE_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GOOGLE_EMBEDDING_DIMENSIONS: int = 768
    # Resolved at runtime (set by EmbeddingService based on provider)
    EMBEDDING_DIMENSIONS: int = 768

    # Processing limits
    PDF_MAX_PAGES: int = 50
    PDF_MAX_SIZE_MB: int = 100

    # Tag evolution
    TAG_EVOLUTION_MIN_DOCS: int = 10
    TAG_MERGE_SIMILARITY_THRESHOLD: float = 0.88
    TAG_SPLIT_DOC_THRESHOLD: int = 15
    TAG_AUTO_APPROVE_CONFIDENCE: float = 0.95


settings = Settings()
