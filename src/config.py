from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenRouterSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENROUTER_")

    api_key: SecretStr = Field(default=SecretStr(""))
    default_model: str = "openai/gpt-4o-mini"
    max_tokens: int = 2048
    temperature: float = 0.3


class EmbeddingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    dimensions: int = 384
    batch_size: int = 32


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    url: str = Field(
        default="sqlite+aiosqlite:///data/app.db",
        validation_alias=AliasChoices("DATABASE__URL", "DATABASE_URL"),
    )

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://") :]
        if value.startswith("postgresql://") and "+asyncpg" not in value:
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS__URL", "REDIS_URL"),
    )


class RateLimitSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")

    requests_per_minute: int = 30
    requests_per_hour: int = 200


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    jwt_secret: SecretStr = Field(default=SecretStr("change-me"))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440


class RerankerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RERANKER_")

    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    top_k: int = 20
    top_n: int = 5


class RetrievalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RETRIEVAL_")

    similarity_threshold: float = 0.7
    context_max_tokens: int = 3000


class SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEED_")

    admin_username: str = "admin"
    admin_password: str = "admin123"
    admin_email: str = "admin@example.com"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    app_name: str = "Support RAG"
    app_url: str = "http://localhost:8080"
    debug: bool = False

    openrouter: OpenRouterSettings = OpenRouterSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    auth: AuthSettings = AuthSettings()
    reranker: RerankerSettings = RerankerSettings()
    retrieval: RetrievalSettings = RetrievalSettings()
    seed: SeedSettings = SeedSettings()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
