from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "AGENTOPS"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 8800
    POSTGRES_DB: str = "agentops"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:8800/agentops"

    # Cache / Message Queue
    REDIS_URL: str = "redis://localhost:6379/0"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_AGENT_EVENTS_TOPIC: str = "agentops.events"

    # Vector / RAG
    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # LLM
    LLM_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = "mock-key-for-local-dev"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0

    # Execution Policy
    EXECUTION_POLICY: str = "ASSISTED"  # "ASSISTED" or "AUTONOMOUS"

    # Guardrails
    MAX_AGENT_ITERATIONS: int = 10
    MAX_TOOL_ITERATIONS: int = 8
    ALLOWED_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("ALLOWED_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


settings = Settings()
