"""Bounded image OCR/Vision analysis with artifact-level caching."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Protocol, cast

from pydantic import Field

from .contracts import CapturedImage, Contract, SilverImage
from .storage import LocalObjectStore

logger = logging.getLogger(__name__)


class VisionPolicy(Contract):
    enabled: bool = True
    max_images_per_page: int = Field(default=4, ge=0, le=50)
    min_width: int = Field(default=250, ge=0)
    min_height: int = Field(default=120, ge=0)
    max_image_bytes: int = Field(default=5_000_000, ge=1)
    allowed_media_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    )


class ImageTextExtractor(Protocol):
    extractor_name: str

    async def extract_text(self, data: bytes, *, media_type: str) -> str: ...


class OpenAICompatibleVision:
    """Vision adapter for OpenAI-compatible chat completion APIs."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model_name: str,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.extractor_name = f"vision:{model_name}"

    async def extract_text(self, data: bytes, *, media_type: str) -> str:
        try:
            import httpx
        except ModuleNotFoundError as error:  # pragma: no cover - optional dependency
            raise RuntimeError("install the 'llm' extra to use Vision OCR") from error
        encoded = base64.b64encode(data).decode("ascii")
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Transcribe every visible Korean and English character exactly. "
                        "Preserve line breaks. Do not describe or infer anything."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Return only text visible in this image."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{encoded}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "image_transcription",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                        "additionalProperties": False,
                    },
                },
            },
        }
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{self.endpoint}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            body: Any = response.json()
        content = body["choices"][0]["message"]["content"]
        value = json.loads(content)
        if not isinstance(value, dict) or not isinstance(value.get("text"), str):
            raise ValueError("Vision response must contain a text string")
        return cast(str, value["text"]).strip()


async def analyze_images(
    images: tuple[CapturedImage, ...],
    *,
    store: LocalObjectStore,
    extractor: ImageTextExtractor | None,
    policy: VisionPolicy,
    cache: dict[str, str] | None = None,
) -> tuple[SilverImage, ...]:
    """Analyze likely text-bearing images and retain metadata for every image."""
    text_cache = cache if cache is not None else {}
    eligible = sorted(
        (
            image
            for image in images
            if image.object is not None
            and image.width >= policy.min_width
            and image.height >= policy.min_height
            and image.object.size <= policy.max_image_bytes
            and image.object.media_type in policy.allowed_media_types
        ),
        key=lambda image: image.width * image.height,
        reverse=True,
    )
    selected = {
        image.url for image in eligible[: policy.max_images_per_page]
    } if policy.enabled and extractor is not None else set()
    output: list[SilverImage] = []
    for image in images:
        text = ""
        error: str | None = None
        if image.url in selected and image.object is not None and extractor is not None:
            digest = image.object.sha256
            if digest in text_cache:
                text = text_cache[digest]
            else:
                try:
                    data = store.get_bytes(image.object)
                    text = await extractor.extract_text(
                        data,
                        media_type=image.object.media_type,
                    )
                    text_cache[digest] = text
                except Exception as exception:
                    error = f"{type(exception).__name__}: {exception}"
                    logger.warning(
                        "image_analysis_failed",
                        extra={"image_url": image.url, "error": error},
                    )
        output.append(
            SilverImage(
                url=image.url,
                alt=image.alt,
                width=image.width,
                height=image.height,
                kind=image.kind,
                artifact_sha256=image.object.sha256 if image.object else None,
                media_type=image.object.media_type if image.object else None,
                extracted_text=text,
                extractor=extractor.extractor_name if text and extractor else None,
                analysis_error=error,
            )
        )
    return tuple(output)
