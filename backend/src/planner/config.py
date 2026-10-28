"""Application settings, loaded from environment variables (prefix ``PLANNER_``) or a ``.env`` file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLANNER_", env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'planner.db'}"

    jwt_secret: str = "dev-only-secret-change-me-in-production-0123456789"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30

    # Which model serves each task (see config/models.yaml).
    models_config_path: Path = BACKEND_DIR / "config" / "models.yaml"

    # Every model call is appended to <llm_log_dir>/<task>.jsonl in chat format,
    # so real usage can later be reviewed and mixed into fine-tuning data.
    llm_log_enabled: bool = True
    llm_log_dir: Path = BACKEND_DIR / "data" / "llm_logs"

    intake_max_questions: int = 10
    chat_context_messages: int = 12
    summary_every_n_messages: int = 16

    # Background check-in scheduler.
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 300

    # Expo push notifications. Off by default: check-ins still land in the in-app inbox.
    push_enabled: bool = False

    cors_origins: list[str] = ["*"]
    dev_endpoints_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
