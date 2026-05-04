from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./jarvis.db"

    telegram_coordinator_bot_token: str = Field(default="", alias="TELEGRAM_COORDINATOR_BOT_TOKEN")
    telegram_frontend_bot_token: str = Field(default="", alias="TELEGRAM_FRONTEND_BOT_TOKEN")
    telegram_backend_bot_token: str = Field(default="", alias="TELEGRAM_BACKEND_BOT_TOKEN")
    telegram_qa_bot_token: str = Field(default="", alias="TELEGRAM_QA_BOT_TOKEN")
    telegram_devops_bot_token: str = Field(default="", alias="TELEGRAM_DEVOPS_BOT_TOKEN")
    telegram_designer_bot_token: str = Field(default="", alias="TELEGRAM_DESIGNER_BOT_TOKEN")
    telegram_manager_bot_token: str = Field(default="", alias="TELEGRAM_MANAGER_BOT_TOKEN")

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    max_rounds_per_task: int = 8
    group_mode: str = "group_showcase"
    llm_timeout_seconds: int = 45
    openai_model: str = "gpt-4.1-mini"
    anthropic_model: str = "claude-3-5-sonnet-latest"

    telegram_group_chat_id: int = Field(default=0, alias="TELEGRAM_GROUP_CHAT_ID")


settings = Settings()
