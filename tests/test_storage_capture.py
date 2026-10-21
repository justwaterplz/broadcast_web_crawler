from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from broadcast_web_crawler.capture import LocalCaptureSession
from broadcast_web_crawler.crawler import CrawlOutput, RawImage, RawPage, ResponseCapture
from broadcast_web_crawler.storage import IntegrityError, LocalObjectStore


def test_content_addressed_objects_are_deduplicated_and_verified(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    first = store.put_bytes(b"same payload", media_type="text/plain")
    second = store.put_bytes(b"same payload", media_type="text/plain")

    assert first == second
    assert store.get_bytes(first) == b"same payload"
    object_path = (
        tmp_path / "objects" / "sha256" / first.sha256[:2] / first.sha256[2:4] / first.sha256
    )
    object_path.write_bytes(b"corrupt")
    with pytest.raises(IntegrityError):
        store.get_bytes(first)


@pytest.mark.asyncio
async def test_capture_session_writes_reproducible_manifest(tmp_path: Path) -> None:
    session = LocalCaptureSession(LocalObjectStore(tmp_path))
    await session(
        ResponseCapture(
            page_url="https://example.com/",
            url="https://example.com/api",
            status=200,
            headers=(("content-type", "application/json"),),
            body=b'{"ok":true}',
            resource_type="xhr",
        )
    )
    await session(
        ResponseCapture(
            page_url="https://example.com/",
            url="https://example.com/hero.jpg",
            status=200,
            headers=(("content-type", "image/jpeg"),),
            body=b"fake-image",
            resource_type="image",
        )
    )
    output = CrawlOutput(
        start_url="https://example.com/",
        pages=(
            RawPage(
                url="https://example.com/",
                depth=0,
                status=200,
                score=0,
                html=b"<html></html>",
                links=(),
                images=(
                    RawImage(
                        url="https://example.com/hero.jpg",
                        alt="program information",
                        width=980,
                        height=820,
                        kind="css-background",
                    ),
                ),
            ),
        ),
        program_urls=(),
        skipped_urls=(),
        total_bytes=26,
        elapsed_seconds=0.1,
    )
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    run_id = UUID("00000000-0000-0000-0000-000000000001")

    manifest, reference = session.finalize(output, run_id=run_id, captured_at=instant)

    assert manifest.pages[0].resources[0].object.media_type == "application/json"
    assert manifest.pages[0].images[0].object is not None
    assert manifest.pages[0].images[0].object.media_type == "image/jpeg"
    assert session.store.exists(reference)
    assert session.store.put_manifest(manifest) == reference
