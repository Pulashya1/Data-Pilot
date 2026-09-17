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
    # §5.8: on a paid provider tier, the call-count cap alone no longer protects a wallet from
    # a stuck retry loop or a runaway session — this is the dollar-denominated backstop for
    # that, checked and accumulated the same way in LLMClient.complete().
    llm_max_cost_per_session_usd: float = 0.50
    llm_rpm_limit: int = 10
    llm_tpm_limit: int = 200_000
    llm_cache_ttl_seconds: int = 86_400
    llm_sample_rows: int = 20
    # Internal tuning knobs (not in .env.example — sane defaults, override only if needed).
    llm_retry_max_attempts: int = 3
    llm_retry_base_delay_seconds: float = 1.0

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
    # The relay container's 5 ZMQ ports are published to the *host's* 127.0.0.1
    # (docker_backend.py's module docstring), which only that literal address reaches when
    # the backend process itself also runs directly on the host. When the backend instead
    # runs inside a container (docker-compose.yml), its own "127.0.0.1" is its own loopback,
    # not the host's — override this to "host.docker.internal" (Docker Desktop resolves it to
    # the host automatically; docker-compose.yml also adds the Linux `host-gateway` fallback).
    kernel_host_address: str = "127.0.0.1"

    # Q&A (Phase 7, MASTER_PROMPT.md §5.5/§5.6)
    qa_max_output_chars: int = 2000

    # App
    env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
