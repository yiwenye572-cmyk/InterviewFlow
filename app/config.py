from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dashscope_api_key: str = ""
    qwen_model: str = "qwen-plus"
    qwen_model_fast: str = "qwen-turbo"
    qwen_embedding_model: str = "text-embedding-v3"
    match_threshold: int = 60
    max_interview_rounds: int = 10
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
    chroma_path: str = str(BASE_DIR / "data" / "chroma")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_settings() -> None:
    settings = get_settings()
    if not settings.dashscope_api_key or settings.dashscope_api_key == "sk-xxx":
        raise RuntimeError(
            "DASHSCOPE_API_KEY is missing. Copy .env.example to .env and set your API key."
        )
