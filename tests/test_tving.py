from __future__ import annotations

import json
from pathlib import Path

import pytest

from broadcast_web_crawler import tving
from broadcast_web_crawler.tving import (
    TvingError,
    content_metadata,
    normalize_content_url,
    parse_detail,
    parse_episodes,
)


def _payload(*, total: int = 1, has_more: str = "N") -> dict:
    return {
        "header": {"status": 200},
        "body": {
            "total_count": total, "has_more": has_more,
            "result": [{
                "vod_name": {"ko": "2화"},
                "episode": {"code": "E002", "frequency": 2, "synopsis": {"ko": "회차 줄거리"}},
            }],
        },
    }


def test_http_success_does_not_mask_api_authorization_error() -> None:
    with pytest.raises(TvingError, match="401"):
        parse_episodes({"header": {"status": 401}, "body": None}, "P001")


def test_incomplete_list_is_never_reported_as_complete() -> None:
    result = parse_episodes(_payload(total=8, has_more="Y"), "P001")
    assert result["complete_for_current_api_listing"] is False
    assert result["episodes"][0]["synopsis"] == "회차 줄거리"


def test_duplicate_episodes_do_not_satisfy_total_count() -> None:
    payload = _payload(total=2)
    payload["body"]["result"] *= 2
    assert parse_episodes(payload, "P001")["complete_for_current_api_listing"] is False


@pytest.mark.parametrize("code", ["P001790587", "E004615360"])
def test_detail_url_normalization(code: str) -> None:
    assert normalize_content_url(f" https://tving.com/contents/{code}/?utm_source=x#info ") == (
        f"https://www.tving.com/contents/{code}", code,
    )


@pytest.mark.parametrize("url", [
    "P001790587", "https://www.tving.com/more/genre/PCA",
    "https://www.tving.com.attacker.test/contents/P001", "http://www.tving.com/contents/P001",
])
def test_non_detail_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_content_url(url)


def test_image_fields_are_excluded_from_all_metadata_sections() -> None:
    props = {
        "contentInfo": {"program_code": "P001", "image": [{"url": "poster.jpg"}],
                        "episode_image": [{"url": "episode.jpg"}], "title": "작품"},
        "preReleaseClipInfo": [{"clip_info": {"image": "clip.jpg", "title": "예고"}}],
        "contentClipInfo": {"items": [{"thumbnail": "thumb.jpg", "title": "클립"}]},
    }
    html = '<script id="__NEXT_DATA__">' + json.dumps({"props": {"pageProps": props}})
    html += '</script><script type="application/ld+json">'
    html += '{"image":"schema.jpg","name":"작품"}</script>'
    result = parse_detail(html)
    serialized = json.dumps(result)
    assert ".jpg" not in serialized
    assert result["content_info"]["title"] == "작품"
    payload = _payload()
    payload["body"]["result"][0]["episode"]["image"] = [{"url": "episode.jpg"}]
    assert "images" not in parse_episodes(payload, "P001")["episodes"][0]


def test_content_document_keeps_show_facts_without_site_or_transport_fields() -> None:
    captured = {
        "source_endpoint": "https://api.tving.com/example",
        "detail": {
            "content_info": {
                "program_code": "P001", "title": "작품", "actor": ["배우"],
                "synopsis": "작품 줄거리", "episode_synopsis": "선택된 회차의 줄거리",
                "view_permission_code": "GUEST", "drm_yn": "Y", "sale_status": 1650,
                "broad_dt": "20260910", "script": None,
            },
            "json_ld": [{"@type": "BreadcrumbList"},
                        {"@type": "TVSeries", "contentRating": "15"}],
        },
        "episode_list": parse_episodes(_payload(), "P001"),
    }
    result = content_metadata(captured)
    assert result["synopsis"] == "작품 줄거리"
    assert result["episodes"][0]["synopsis"] == "회차 줄거리"
    assert result["cast"] == ["배우"]
    assert result["writers"] is None
    assert result["broadcast_start_date"] == "2026-09-10"
    assert result["age_rating"] == "15"
    serialized = json.dumps(result)
    for field in ("source_endpoint", "view_permission_code", "drm_yn", "sale_status",
                  "json_ld", "api_status", "grade_code", "free_yn", "episode_synopsis"):
        assert field not in serialized


def test_collection_stores_source_payloads_once_in_one_bundle(
    tmp_path: Path, monkeypatch,
) -> None:
    props = {"contentInfo": {"program_code": "P001", "title": "작품",
                             "director": ["연출자", "작가"], "broad_dt": 20260910,
                             "script": None, "image": [{"url": "poster.jpg"}],
                             "extra_source_field": {"flag": False, "count": 0, "code": "001"}}}
    html = '<script id="__NEXT_DATA__">' + json.dumps({"props": {"pageProps": props}})
    html += '</script><script src="/_next/static/chunks/pages/_app-test.js"></script>'
    json_ld = {"@type": "TVSeries", "contentRating": "15", "image": "schema.jpg"}
    html += '<script type="application/ld+json">' + json.dumps(json_ld) + '</script>'
    api = _payload(total=8, has_more="Y")
    api["body"]["result"][0]["episode"].update(
        broadcast_date=20260910, image=[{"url": "episode.jpg"}], free_yn="N",
    )
    api["body"]["unmapped_field"] = [None, False, "001", 0]
    raw_api = json.dumps(api, ensure_ascii=False, indent=2) + "\r\n"

    def get(url):
        if "/contents/" in url:
            return html
        if "_app-" in url:
            return '46900:function(){var b="public-test-key"}'
        return raw_api

    monkeypatch.setattr(tving, "_get_text", get)
    tving.collect_program_with_report("https://www.tving.com/contents/P001", tmp_path)
    bundle = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert bundle["contentInfo"] == props["contentInfo"]
    assert bundle["jsonLd"] == [json_ld]
    assert bundle["episodeApi"] == api
    assert sorted(p.name for p in tmp_path.iterdir()) == ["metadata.json"]
    assert not (tmp_path / "page.html").exists()
    assert bundle["collection"]["acquisition_method"] == "embedded_page_data_and_episode_api"
    assert bundle["collection"]["complete_for_current_api_listing"] is False
    assert "public-test-key" not in json.dumps(bundle)


def test_raw_api_error_response_survives_display_parser_failure(tmp_path: Path, monkeypatch):
    html = '<script id="__NEXT_DATA__">' + json.dumps({"props": {"pageProps": {
        "contentInfo": {"program_code": "P001", "title": "작품", "director": None},
    }}}) + '</script><script src="/_next/static/chunks/pages/_app-test.js"></script>'
    raw_api = '{"header":{"status":401,"message":"source error"},"body":null}'

    def get(url):
        if "/contents/" in url:
            return html
        if "_app-" in url:
            return '46900:function(){var b="public-test-key"}'
        return raw_api

    monkeypatch.setattr(tving, "_get_text", get)
    with pytest.raises(TvingError, match="401"):
        tving.collect_program_with_report("https://www.tving.com/contents/P001", tmp_path)
    bundle = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert bundle["episodeApi"] == json.loads(raw_api)
    assert bundle["collection"]["status"] == "display_parser_failed"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["metadata.json"]


def test_public_client_key_follows_export_instead_of_url_variable():
    from broadcast_web_crawler.tving import extract_public_client_key

    script = '46900:function(e,t,n){n.d(t,{q1:function(){return y}});var b="https://",y="current-key"}'
    assert extract_public_client_key(script) == "current-key"
    with pytest.raises(TvingError):
        extract_public_client_key('46900:function(){var b="https://"}')
