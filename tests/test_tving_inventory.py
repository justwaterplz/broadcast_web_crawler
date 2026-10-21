import json

from broadcast_web_crawler import tving_batch, tving_inventory
from broadcast_web_crawler.tving_inventory import scan_inventory, validate_inventory


def listing_html():
    data = {
        "order": "hit",
        "band": {
            "items": [{"code": "P001", "title": "작품1"}],
            "nextApiUrl": "/bff/web/v3/content/vod?pageNo=2",
        },
    }
    props = {
        "dehydratedState": {
            "queries": [
                {
                    "queryKey": ["/bff/web/v3/more/genre/PCA"],
                    "state": {"data": {"pages": [{"data": data}]}},
                }
            ]
        }
    }
    return '<script id="__NEXT_DATA__">' + json.dumps({"props": {"pageProps": props}}) + "</script>"


def test_inventory_counts_unique_ids_and_follows_listing_end(tmp_path, monkeypatch):
    page2 = {
        "code": "0000",
        "data": {
            "items": [
                {"code": "P001", "title": "작품1"},
                {"code": "P002", "title": "작품2"},
            ],
            "nextApiUrl": None,
        },
    }
    monkeypatch.setattr(
        tving_batch,
        "_get_text",
        lambda url: listing_html() if "/more/genre/" in url else json.dumps(page2),
    )
    monkeypatch.setattr(tving_batch.time, "sleep", lambda _: None)
    report, path = scan_inventory(tmp_path, url=tving_batch.LISTING_URL)
    assert report["unique_count"] == 2
    assert report["duplicate_items_count"] == 1
    assert report["pages_read"] == 2 and report["complete_listing"] is True
    assert [p["url"] for p in report["programs"]] == [
        "https://www.tving.com/contents/P001",
        "https://www.tving.com/contents/P002",
    ]
    assert json.loads(path.read_text(encoding="utf-8")) == report
    validate_inventory(report, url=tving_batch.LISTING_URL, category="drama")


def test_inventory_page_cap_keeps_partial_list_without_claiming_total(tmp_path, monkeypatch):
    monkeypatch.setattr(tving_batch, "_get_text", lambda _: listing_html())
    report, path = scan_inventory(tmp_path, url=tving_batch.LISTING_URL, max_pages=1)
    assert report["complete_listing"] is False
    assert report["unique_count"] == 1 and "page limit" in report["error"]
    assert json.loads(path.read_text(encoding="utf-8"))["programs"] == report["programs"]


def test_inventory_repeated_cursor_is_not_infinite(tmp_path, monkeypatch):
    page = {
        "code": "0000",
        "data": {
            "items": [{"code": "P001", "title": "작품1"}],
            "nextApiUrl": "/bff/web/v3/content/vod?pageNo=2",
        },
    }
    monkeypatch.setattr(
        tving_batch,
        "_get_text",
        lambda url: listing_html() if "/more/genre/" in url else json.dumps(page),
    )
    monkeypatch.setattr(tving_batch.time, "sleep", lambda _: None)
    report, _ = scan_inventory(tmp_path, url=tving_batch.LISTING_URL)
    assert report["complete_listing"] is False and report["pages_read"] == 2
    assert "repeated" in report["error"]


def test_saved_inventory_collection_uses_fixed_urls_without_discovering_again(
    tmp_path, monkeypatch
):
    inventory = {
        "format": tving_inventory.INVENTORY_FORMAT,
        "source_url": tving_batch.LISTING_URL,
        "category": "drama",
        "subcategory": "전체",
        "complete_listing": True,
        "order": "hit",
        "pages_read": 1,
        "unique_count": 1,
        "checked_at": "2026-10-12T12:00:00+09:00",
        "programs": [
            {
                "rank": 1,
                "title": "작품1",
                "url": "https://www.tving.com/contents/P001",
            }
        ],
    }

    def unexpected(*args, **kwargs):
        raise AssertionError("Do not rediscover a completed inventory")

    monkeypatch.setattr(tving_batch, "discover_programs", unexpected)
    monkeypatch.setattr(tving_batch, "category_name", unexpected)
    monkeypatch.setattr(tving_batch.time, "sleep", lambda _: None)

    def collect(url, output):
        assert url == inventory["programs"][0]["url"]
        return {
            "metadata_file": "metadata.json",
            "bundle": {"contentInfo": {"title": "작품1"}},
            "episode_list": {
                "episodes": [],
                "collected_count": 0,
                "complete_for_current_api_listing": True,
            },
        }

    monkeypatch.setattr(tving_batch, "collect_program_with_report", collect)
    report = tving_batch.collect_top_programs(tmp_path, limit=None, inventory=inventory)
    assert report["summary"]["successful_programs"] == 1
    assert report["listing"]["inventory_checked_at"] == inventory["checked_at"]
