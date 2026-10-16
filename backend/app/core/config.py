from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"

    data_dir: Path = Path("../data")
    database_url: str = "sqlite:///../data/app.db"

    latex_compiler: str = "xelatex"
    latex_timeout_seconds: int = 60
    latex_max_repair_attempts: int = 5
    latex_max_pages: int = 2

    llm_provider: str = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_workspace_id: str = ""
    openai_compatible_base_url: str = ""

    llm_model_analysis: str = "claude-haiku-4-5"
    llm_model_matching: str = "claude-sonnet-5"
    llm_model_drafting: str = "claude-sonnet-5"
    llm_model_fact_check: str = "claude-sonnet-5"
    llm_model_ats: str = "claude-haiku-4-5"
    llm_model_style: str = "claude-sonnet-5"

    max_generation_cost_usd: float = 1.00

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    http_user_agent: str = "cv-application-manager/0.1 (+local)"
    http_timeout_seconds: int = 15

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def profile_dir(self) -> Path:
        return self.data_dir / "profile"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"


@lru_cache
def get_settings() -> Settings:
    return Settings()
