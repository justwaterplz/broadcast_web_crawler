"""Runnable API composition root."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from .api import create_app
from .crawler import CrawlPolicy, PlaywrightCrawler
from .database import MetadataRepository
from .normalization import MetadataNormalizer, OpenAICompatibleLLM
from .orchestrator import Pipeline
from .settings import Settings
from .storage import LocalObjectStore
from .vision import OpenAICompatibleVision, VisionPolicy


def build_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    config.object_store_root.mkdir(parents=True, exist_ok=True)
    repository = MetadataRepository(config.database_url)
    repository.create_schema()
    provider = OpenAICompatibleLLM(
        endpoint=config.llm_endpoint,
        api_key=config.llm_api_key,
        model_name=config.llm_model,
    )
    vision = OpenAICompatibleVision(
        endpoint=config.llm_endpoint,
        api_key=config.llm_api_key,
        model_name=config.vision_model,
    )
    pipeline = Pipeline(
        crawler=PlaywrightCrawler(
            CrawlPolicy(
                max_pages=config.max_pages,
                max_duration_seconds=config.max_duration_seconds,
                max_total_bytes=config.max_total_bytes,
            )
        ),
        store=LocalObjectStore(config.object_store_root),
        repository=repository,
        normalizer=MetadataNormalizer(provider),
        image_extractor=vision,
        vision_policy=VisionPolicy(
            enabled=config.vision_enabled,
            max_images_per_page=config.vision_max_images_per_page,
        ),
    )
    return create_app(pipeline)


def run() -> None:  # pragma: no cover - process boundary
    uvicorn.run(
        "broadcast_web_crawler.main:build_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
    )
