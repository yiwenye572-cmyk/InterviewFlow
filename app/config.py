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
    screen_concurrency: int = 3
    max_interview_rounds: int = 10
    public_base_path: str = ""
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
    chroma_path: str = str(BASE_DIR / "data" / "chroma")

    volc_speech_api_key: str = ""
    volc_asr_resource_id: str = "volc.seedasr.sauc.duration"
    volc_tts_resource_id: str = "seed-tts-2.0"
    volc_tts_speaker_tech: str = "zh_male_jingqiangkanye_moon_bigtts"
    volc_tts_speaker_hr: str = "zh_female_vv_uranus_bigtts"

    llm_log_enabled: bool = True
    llm_log_path: str = "data/llm_calls.jsonl"
    llm_timeout_default: int = 30
    llm_timeout_report: int = 60
    llm_timeout_stream: int = 120
    llm_max_system_chars: int = 8000
    llm_max_user_chars: int = 12000
    llm_structured_max_retries: int = 2
    llm_trace_backend: str = "none"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_settings() -> None:
    settings = get_settings()
    if not settings.dashscope_api_key or settings.dashscope_api_key == "sk-xxx":
        raise RuntimeError(
            "DASHSCOPE_API_KEY is missing. Copy .env.example to .env and set your API key."
        )
