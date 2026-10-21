"""Environment-backed runtime settings; secrets are never persisted in run payloads."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_url: str = "sqlite+pysqlite:///data/metadata.db"
    object_store_root: Path = Path("data")
    llm_endpoint: str = "https://api.openai.com/v1"
    llm_api_key: str
    llm_model: str = "gpt-4.1-mini"
    vision_enabled: bool = True
    vision_model: str = "gpt-4.1-mini"
    vision_max_images_per_page: int = Field(default=4, ge=0, le=50)
    max_pages: int = Field(default=100, ge=1, le=10_000)
    max_duration_seconds: float = Field(default=900, gt=0)
    max_total_bytes: int = Field(default=250_000_000, gt=0)

    @classmethod
    def from_env(cls) -> Settings:
        api_key = os.getenv("BROADCAST_LLM_API_KEY")
        if not api_key:
            raise RuntimeError("BROADCAST_LLM_API_KEY is required")
        return cls(
            database_url=os.getenv(
                "BROADCAST_DATABASE_URL",
                "sqlite+pysqlite:///data/metadata.db",
            ),
            object_store_root=Path(os.getenv("BROADCAST_OBJECT_STORE_ROOT", "data")),
            llm_endpoint=os.getenv(
                "BROADCAST_LLM_ENDPOINT",
                "https://api.openai.com/v1",
            ),
            llm_api_key=api_key,
            llm_model=os.getenv("BROADCAST_LLM_MODEL", "gpt-4.1-mini"),
            vision_enabled=os.getenv(
                "BROADCAST_VISION_ENABLED",
                "true",
            ).casefold()
            in {"1", "true", "yes", "on"},
            vision_model=os.getenv(
                "BROADCAST_VISION_MODEL",
                os.getenv("BROADCAST_LLM_MODEL", "gpt-4.1-mini"),
            ),
            vision_max_images_per_page=int(
                os.getenv("BROADCAST_VISION_MAX_IMAGES_PER_PAGE", "4")
            ),
            max_pages=int(os.getenv("BROADCAST_MAX_PAGES", "100")),
            max_duration_seconds=float(
                os.getenv("BROADCAST_MAX_DURATION_SECONDS", "900")
            ),
            max_total_bytes=int(
                os.getenv("BROADCAST_MAX_TOTAL_BYTES", "250000000")
            ),
        )
