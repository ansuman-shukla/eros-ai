"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application settings loaded from environment variables."""

    # FastAPI / Auth
    SECRET_KEY: str = "change-me-to-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # MongoDB
    MONGODB_URI: str = "mongodb+srv://ansuman-shukla:ansuman@cluster0.zkpcq.mongodb.net/?appName=Cluster0"
    MONGODB_DB: str = "eros_ai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # LiveKit
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""

    # Deepgram (STT + TTS)
    DEEPGRAM_API_KEY: str = ""

    # Cerebras (via LiveKit OpenAI plugin)
    CEREBRAS_API_KEY: str = ""

    # Gemini (memory retrieval + pipelines)
    GEMINI_API_KEY: str = ""

    # ARQ worker
    ARQ_REDIS_URL: str = "redis://localhost:6379"
    DIARY_CRON_HOUR: int = 23
    DIARY_CRON_MINUTE: int = 59

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
