from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

WhisperModel = Literal["whisper-large-v3-turbo", "whisper-large-v3"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""

    # Model names
    gemini_model: str = "gemini-2.5-flash-lite"
    qwen_model: str = "qwen/qwen3-vl-30b-a3b-instruct"
    embedding_model: str = "gemini-embedding-001"
    whisper_models: list[WhisperModel] = ["whisper-large-v3-turbo", "whisper-large-v3"]

    # Storage paths (relative to cwd or absolute)
    atlas_home: str = str(Path.home() / ".atlas")

    # Inference
    embedding_dim: int = 768
    enable_logging: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Task Queue and Concurrency
    process_workers: int = 8
    default_queue_workers: int = 2
    max_queue_workers: int = 2

    @property
    def zvec_store_root(self) -> Path:
        """Get absolute path to zvec store root directory"""
        p = Path(self.atlas_home)
        return p / "index"


settings = Settings()
