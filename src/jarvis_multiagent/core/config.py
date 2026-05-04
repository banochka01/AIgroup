from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    database_url: str = Field(default="sqlite+aiosqlite:///./jarvis.db", alias="DATABASE_URL")

    telegram_coordinator_bot_token: str = Field(default="", alias="TELEGRAM_COORDINATOR_BOT_TOKEN")
    telegram_frontend_bot_token: str = Field(default="", alias="TELEGRAM_FRONTEND_BOT_TOKEN")
    telegram_backend_bot_token: str = Field(default="", alias="TELEGRAM_BACKEND_BOT_TOKEN")
    telegram_qa_bot_token: str = Field(default="", alias="TELEGRAM_QA_BOT_TOKEN")
    telegram_devops_bot_token: str = Field(default="", alias="TELEGRAM_DEVOPS_BOT_TOKEN")
    telegram_designer_bot_token: str = Field(default="", alias="TELEGRAM_DESIGNER_BOT_TOKEN")
    telegram_manager_bot_token: str = Field(default="", alias="TELEGRAM_MANAGER_BOT_TOKEN")
    telegram_group_chat_id: int = Field(default=0, alias="TELEGRAM_GROUP_CHAT_ID")

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    max_rounds_per_task: int = Field(default=6, alias="MAX_ROUNDS_PER_TASK")
    max_messages_per_task: int = Field(default=40, alias="MAX_MESSAGES_PER_TASK")
    group_mode: str = Field(default="group_showcase", alias="GROUP_MODE")
    llm_timeout_seconds: int = Field(default=45, alias="LLM_TIMEOUT_SECONDS")
    llm_max_output_tokens: int = Field(default=900, alias="LLM_MAX_OUTPUT_TOKENS")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")

    sandbox_timeout_seconds: int = Field(default=30, alias="SANDBOX_TIMEOUT_SECONDS")
    sandbox_max_output_chars: int = Field(default=12000, alias="SANDBOX_MAX_OUTPUT_CHARS")


settings = Settings()
