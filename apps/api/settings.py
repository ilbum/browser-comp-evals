from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://eval:eval@localhost:5432/eval_db"
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "browsecomp-eval"

    anthropic_api_key: str = ""
    brave_search_api_key: str = ""

    log_level: str = "INFO"


settings = Settings()
