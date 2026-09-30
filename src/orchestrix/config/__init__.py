"""ORCHESTRIX — Configuration chargée depuis .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings globaux. Chargés depuis variables d'environnement / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = True
    app_log_level: str = "INFO"
    app_secret_key: str = "change-me"

    # ── API ────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:8501"

    # ── PostgreSQL ─────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "orchestrix"
    postgres_user: str = "orchestrix"
    postgres_password: str = "orchestrix_dev"
    database_url: str = "postgresql+asyncpg://orchestrix:orchestrix_dev@localhost:5432/orchestrix"

    # ── Redis ──────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_url: str = "redis://localhost:6379/0"

    # ── MLflow ─────────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_artifact_root: str = "./mlartifacts"
    mlflow_experiment_name: str = "orchestrix-dev"

    # ── LLM ────────────────────────────────────────────────────────
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:3b"

    llm_fallback_provider: str | None = None
    llm_fallback_base_url: str | None = None
    llm_fallback_api_key: str | None = None
    llm_fallback_model: str | None = None

    # ── Embeddings ─────────────────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # ── Jira ───────────────────────────────────────────────────────
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "PROJ"
    jira_demo_project_key: str = "DEMO"

    # ── Observabilité ──────────────────────────────────────────────
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # ── Evaluation gate ────────────────────────────────────────────
    eval_gate_max_unsafe_action_rate_increase: float = 0.05
    eval_gate_min_task_success: float = 0.80
    eval_gate_max_false_block_rate: float = 0.10

    # ── ActionGuard ────────────────────────────────────────────────
    actionguard_human_review_threshold: float = 0.5
    actionguard_max_daily_actions_per_user: int = 20
    actionguard_max_assigned_hours_per_week: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
