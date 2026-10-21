from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from broadcast_web_crawler import tving_batch
from broadcast_web_crawler.tving import TvingError
from broadcast_web_crawler.tving_batch import (
    KST,
    create_run_folder,
    discover_programs,
    parse_listing,
    safe_folder_name,
)


def _listing_html(items: list[dict]) -> str:
    payload = {"props": {"pageProps": {"dehydratedState": {"queries": [{
        "queryKey": ["/bff/web/v3/more/genre/PCA"],
        "state": {"data": {"pages": [{"data": {
            "order": "hit", "band": {"items": items},
        }}]}},
    }]}}}}
    return '<script id="__NEXT_DATA__">' + json.dumps(payload) + '</script>'


def test_listing_preserves_order_and_does_not_count_duplicates_or_images() -> None:
    items = [{"code": f"P{n:03}", "title": f"작품 {n}", "imageUrl": "poster.jpg"}
             for n in range(21)]
    items.insert(1, items[0])
    result = parse_listing(_listing_html(items))
    assert len(result["programs"]) == 20
    assert result["programs"][-1]["url"].endswith("P019")
    assert "poster.jpg" not in json.dumps(result)
    assert result["order"] == "hit"


def test_short_listing_does_not_silently_reduce_collection_scope() -> None:
    with pytest.raises(TvingError, match="only 1"):
        parse_listing(_listing_html([{"code": "P001", "title": "작품"}]))


def test_repeat_runs_use_unique_timestamp_and_category_folders(tmp_path: Path) -> None:
    now = datetime(2026, 10, 7, 22, 0, 0, tzinfo=KST)
    first = create_run_folder(tmp_path, "예능", "여행/먹방", now)
    second = create_run_folder(tmp_path, "예능", "여행/먹방", now)
    assert first != second
    assert first.name == "20261007_220000_000000_예능_여행_먹방"
    assert second.exists()
    assert safe_folder_name('제목: "예고"?') == "제목_ _예고__"
    assert safe_folder_name("CON") == "_CON"


def test_requested_rank_range_follows_api_and_deduplicates(monkeypatch) -> None:
    first = [{"code": "P001", "title": "작품1"}, {"code": "P002", "title": "작품2"}]
    html = _listing_html(first)
    html = html.replace('"items":', '"nextApiUrl": "/bff/web/v3/content/vod?pageNo=2", "items":')
    payload = {"code": "0000", "data": {"items": [
        {"code": "P002", "title": "작품2"}, {"code": "P003", "title": "작품3"},
    ], "nextApiUrl": None}}
    calls = []

    def get(url: str) -> str:
        calls.append(url)
        return html if len(calls) == 1 else json.dumps(payload)

    monkeypatch.setattr(tving_batch, "_get_text", get)
    monkeypatch.setattr(tving_batch.time, "sleep", lambda _: None)
    result = discover_programs(tving_batch.LISTING_URL, limit=1, start_rank=3, max_pages=2)
    assert len(calls) == 2
    assert result["programs"] == [{"rank": 3, "title": "작품3",
                                    "url": "https://www.tving.com/contents/P003"}]


def test_page_bound_does_not_mark_partial_category_as_all(monkeypatch) -> None:
    html = _listing_html([{"code": "P001", "title": "작품"}])
    html = html.replace('"items":', '"nextApiUrl": "/bff/web/v3/content/vod?pageNo=2", "items":')
    monkeypatch.setattr(tving_batch, "_get_text", lambda _: html)
    with pytest.raises(TvingError, match="page limit"):
        discover_programs(tving_batch.LISTING_URL, limit=None, start_rank=1, max_pages=1)
