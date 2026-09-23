from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Literal, List
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: Literal["development", "production"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    secret_key: str = "change-me"

    # Database
    database_url: str = "sqlite+aiosqlite:///./frontier.db"

    # LLM
    llm_provider: Literal["ollama", "lmstudio"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_model: str = "local-model"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    llm_context_length: int = 8192

    # Discord
    discord_bot_token: str = ""
    discord_guild_id: str = ""
    discord_application_id: str = ""

    # X
    x_client_id: str = ""
    x_client_secret: str = ""
    x_bearer_token: str = ""

    # Web Search
    search_provider: str = "duckduckgo"
    serpapi_key: str = ""

    # Content
    min_relevance_score: float = 0.70
    min_credibility_score: float = 0.65
    max_posts_per_day: int = 20
    default_auto_publish: bool = False

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def llm_base_url(self) -> str:
        if self.llm_provider == "ollama":
            return self.ollama_base_url
        return self.lmstudio_base_url

    @property
    def llm_model(self) -> str:
        if self.llm_provider == "ollama":
            return self.ollama_model
        return self.lmstudio_model

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
