from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore
except ImportError:
    try:
        # Hỗ trợ nếu người dùng dùng pydantic v1
        from pydantic import BaseSettings  # type: ignore
        SettingsConfigDict = None
    except ImportError:
        # Fallback thuần Python nếu môi trường chưa kịp cài pydantic / pydantic-settings
        class BaseSettings:  # type: ignore
            def __init__(self, **kwargs):
                for k, v in self.__class__.__dict__.items():
                    if not k.startswith("_") and not callable(v) and not isinstance(v, property):
                        setattr(self, k, os.getenv(k, v))
                for k, v in kwargs.items():
                    setattr(self, k, v)
        SettingsConfigDict = None


class Settings(BaseSettings):
    """Cấu hình ứng dụng theo đặc tả Mục 14.6."""
    
    # Storage Roots
    SNAPSHOT_ROOT: str = "./data/snapshots"
    CONTROL_ROOT: str = "./data/control"
    MODEL_ROOT: str = "./models"
    
    # Domain & CORS
    PUBLIC_ORIGIN: str = "http://localhost:3000"
    
    # Gemini LLM Config
    GEMINI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    LLM_PROVIDER: str = "gemini_developer"
    LLM_BILLING_MODE: str = "free_only"
    
    # Embedding Model Config (Frozen)
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    EMBEDDING_REVISION: str = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
    
    # Application Limits & Deadlines
    QA_DEADLINE_SECONDS: int = 30
    QA_IP_RPM: int = 5
    QA_MAX_CONCURRENT: int = 1
    APP_CONTEXT_BUDGET: int = 8192
    OUTPUT_RESERVE: int = 2048

    # Tìm file .env ở cả thư mục hiện tại lẫn thư mục cha (khi chạy từ api/)
    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=(".env", "../.env"),
            env_file_encoding="utf-8",
            extra="ignore"
        )
    else:
        class Config:
            env_file = (".env", "../.env")
            env_file_encoding = "utf-8"
            extra = "ignore"

    @property
    def snapshot_path(self) -> Path:
        return Path(self.SNAPSHOT_ROOT)

    @property
    def control_path(self) -> Path:
        return Path(self.CONTROL_ROOT)

    @property
    def model_path(self) -> Path:
        return Path(self.MODEL_ROOT)


settings = Settings()
