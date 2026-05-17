from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Dealer Returns AI Automation"
    environment: str = "dev"

    # Hugging Face Inference configuration
    hf_token: str | None = None
    hf_ocr_model: str = "microsoft/trocr-base-handwritten"
    hf_llm_model: str = "HuggingFaceH4/zephyr-7b-beta"

    # Business controls from requirement deck
    auto_apply_threshold: float = 0.80
    max_image_size_mb: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
