from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from broadcast_web_crawler.contracts import CapturedImage
from broadcast_web_crawler.normalization import MetadataNormalizer
from broadcast_web_crawler.parsing import parse_html
from broadcast_web_crawler.storage import LocalObjectStore
from broadcast_web_crawler.vision import VisionPolicy, analyze_images


class FakeVision:
    extractor_name = "fake-vision/1"
    calls = 0

    async def extract_text(self, data: bytes, *, media_type: str) -> str:
        self.calls += 1
        assert data == b"image-with-korean-text"
        assert media_type == "image/jpeg"
        return "연출: 장세일\n매주 수요일 오후 6시 5분"


class ImageAwareLLM:
    model_name = "fake-metadata-model"

    async def extract(
        self,
        *,
        system: str,
        document: str,
        json_schema: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        assert "연출: 장세일" in document
        return {
            "entities": [
                {
                    "entity_type": "program",
                    "natural_key": "생방송 활기찬 저녁",
                    "fields": [
                        {
                            "path": "director",
                            "value": "장세일",
                            "confidence": 0.95,
                            "evidence": [
                                {
                                    "locator": "image",
                                    "quote": "연출: 장세일",
                                }
                            ],
                        }
                    ],
                }
            ],
            "warnings": [],
        }


@pytest.mark.asyncio
async def test_image_text_is_cached_and_becomes_image_evidence(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    reference = store.put_bytes(
        b"image-with-korean-text",
        media_type="image/jpeg",
    )
    captured = (
        CapturedImage(
            url="https://example.test/program-hero.jpg",
            width=980,
            height=820,
            kind="css-background",
            object=reference,
        ),
    )
    extractor = FakeVision()
    cache: dict[str, str] = {}
    images = await analyze_images(
        captured,
        store=store,
        extractor=extractor,
        policy=VisionPolicy(),
        cache=cache,
    )
    await analyze_images(
        captured,
        store=store,
        extractor=extractor,
        policy=VisionPolicy(),
        cache=cache,
    )
    assert extractor.calls == 1
    assert images[0].extracted_text.startswith("연출:")

    document = parse_html(
        "<html><title>생방송 활기찬 저녁</title><body>프로그램</body></html>",
        source_url="https://example.test/program",
    ).model_copy(update={"images": images})
    result = await MetadataNormalizer(ImageAwareLLM()).normalize(document)
    evidence = result.assertions[0].evidence[0]
    assert evidence.source_url == captured[0].url
    assert evidence.artifact_sha256 == reference.sha256
    assert evidence.locator.startswith("image:")
