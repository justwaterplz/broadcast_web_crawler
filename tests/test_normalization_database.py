from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest

from broadcast_web_crawler.contracts import CrawlPhase, CrawlRun
from broadcast_web_crawler.database import MetadataRepository
from broadcast_web_crawler.normalization import MetadataNormalizer
from broadcast_web_crawler.parsing import parse_html


class FakeLLM:
    model_name = "fake-model"

    async def extract(
        self,
        *,
        system: str,
        document: str,
        json_schema: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        assert "Do not infer" in system
        assert json_schema["type"] == "object"
        return {
            "entities": [
                {
                    "entity_type": "program",
                    "natural_key": "테스트 쇼",
                    "fields": [
                        {
                            "path": "name",
                            "value": "테스트 쇼",
                            "confidence": 0.99,
                            "evidence": [{"locator": "title", "quote": "테스트 쇼"}],
                        },
                        {
                            "path": "shootingLocation",
                            "value": "달",
                            "confidence": 0.2,
                            "evidence": [{"locator": "body", "quote": "달에서 촬영"}],
                        },
                    ],
                }
            ],
            "warnings": [],
        }


@pytest.mark.asyncio
async def test_normalizer_rejects_unsupported_evidence_and_persists() -> None:
    html = "<html><head><title>테스트 쇼</title></head><body>출연: 홍길동</body></html>"
    digest = hashlib.sha256(html.encode()).hexdigest()
    document = parse_html(html, source_url="https://example.test/program/1")
    result = await MetadataNormalizer(FakeLLM()).normalize(document)

    assert result.entities[0].attributes == {"name": "테스트 쇼"}
    assert [item.field_path for item in result.assertions] == ["name"]
    assert any("shootingLocation" in warning for warning in result.warnings)
    assert result.assertions[0].evidence[0].artifact_sha256 == digest

    repository = MetadataRepository("sqlite+pysqlite:///:memory:")
    repository.create_schema()
    run = CrawlRun(start_url=document.source_url)
    repository.save_run(run)
    repository.save_run(run.transition(CrawlPhase.DISCOVERING))
    assert repository.get_run(run.run_id).phase is CrawlPhase.DISCOVERING  # type: ignore[union-attr]
    reviews = repository.save_result(uuid4(), result)
    assert reviews == ()
    assert repository.save_result(uuid4(), result) == ()
    assert repository.list_entities()[0]["natural_key"] == "테스트 쇼"
