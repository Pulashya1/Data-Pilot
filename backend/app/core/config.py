"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_model: str = "mock"
    llm_fallbacks: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    ollama_api_base: str = "http://localhost:11434"
    llm_max_calls_per_session: int = 150
    llm_rpm_limit: int = 10
    llm_tpm_limit: int = 200_000
    llm_cache_ttl_seconds: int = 86_400
    llm_sample_rows: int = 20

    # Infra
    database_url: str = "postgresql+asyncpg://datapilot:datapilot@localhost:5432/datapilot"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "datapilot-uploads"

    # Uploads & profiling (Phase 1)
    max_upload_size_mb: int = 200
    preview_row_limit: int = 500
    sample_row_threshold: int = 1_000_000
    sample_size: int = 100_000

    # Sandboxed kernel execution (Phase 2)
    kernel_image: str = "datapilot-kernel:latest"
    kernel_relay_image: str = "datapilot-kernel-relay:latest"
    kernel_network_internal: str = "datapilot-kernel-internal"
    kernel_network_public: str = "datapilot-kernel-public"
    kernel_memory_limit: str = "1g"
    kernel_cpu_limit: float = 1.0
    kernel_idle_timeout_minutes: int = 30
    kernel_cell_timeout_seconds: int = 120
    kernel_startup_timeout_seconds: int = 60

    # App
    env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
