from __future__ import annotations

import json
from pathlib import Path

import pytest

from broadcast_web_crawler import namuwiki
from broadcast_web_crawler.namuwiki import classify_document, parse_document, resolve_document

HTML = """
<html><title>방송 - 나무위키</title><h1>방송</h1>
<table><tr><td>관련 문서</td><td>다른 시즌 출연자</td></tr></table>
<table>
 <tr><td>장르</td><td>예능, 쿡방</td></tr>
 <tr><td>채널</td><td>JTBC</td></tr>
 <tr><td>방송 기간</td><td>2014년 11월 17일 ~ 2019년 11월 25일</td></tr>
 <tr><td>방송 횟수</td><td>254부작</td></tr>
 <tr><td>제작진</td><td>연출 : 감독1, 감독2 조연출 : 보조 작가 : 작가1, 작가2</td></tr>
 <tr><td>출연</td><td>셰프 군단 문서 참조</td></tr>
</table>
<div><div><h2>1. 개요 [편집]</h2></div></div>
<div><p>프로그램 소개 <img src="image.jpg">내용.</p></div>
<h2>2. 논란 [편집]</h2><p>추출하지 않을 내용.</p>
</html>
"""


def test_title_and_encoded_title_resolve_to_same_document() -> None:
    url = resolve_document("냉장고를 부탁해")
    assert "%20" in url
    assert resolve_document("냉장고를%20부탁해") == url
    assert resolve_document(url + "?from=test#개요") == url


@pytest.mark.parametrize("url", ["https://namu.wiki.attacker.test/w/방송",
                                 "https://namu.wiki/edit/방송", "http://namu.wiki/w/방송"])
def test_invalid_domains_and_non_document_paths_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        resolve_document(url)


def test_soft_not_found_and_access_denial_are_distinct() -> None:
    assert classify_document("<h1>문서</h1>해당 문서가 존재하지 않습니다", 200) == "not_found"
    assert classify_document("<title>Just a moment...</title>", 200) == "access_denied"
    assert classify_document("blocked", 403) == "access_denied"
    assert classify_document("unknown shell", 200) == "unknown"
    assert classify_document(HTML, 200) == "exists"


def test_content_uses_infobox_and_scoped_sections_without_invented_cast() -> None:
    content, report = parse_document(HTML, resolve_document("방송"))
    assert content["title"] == "방송"
    assert content["directors"] == ["감독1", "감독2"]
    assert content["writers"] == ["작가1", "작가2"]
    assert content["broadcast_start_date"] == "2014-11-17"
    assert content["episode_count"] == 254
    assert content["cast"] is None
    assert content["episodes"] == []
    assert "프로그램 소개" in content["synopsis"]
    assert "추출하지 않을" not in json.dumps(content, ensure_ascii=False)
    assert "image.jpg" not in json.dumps(content)
    assert report["episode_details_collected"] is False


def test_collection_saves_wiki_review_record_separately_from_content(tmp_path, monkeypatch):
    monkeypatch.setattr(namuwiki, "fetch_document", lambda _: (HTML, {
        "requested_url": "https://namu.wiki/w/방송", "final_url": "https://namu.wiki/w/방송",
        "status": "exists", "checked_at": "2026-10-12T12:00:00+09:00",
    }))
    report = namuwiki.collect_document("https://namu.wiki/w/방송", tmp_path)
    assert report["extraction_status"] == "collected"
    record = json.loads(Path(report["source_record_file"]).read_text(encoding="utf-8"))
    content = json.loads(Path(report["content_file"]).read_text(encoding="utf-8"))
    assert record["review"]["status"] == "pending"
    assert record["evidence"]["infobox_fields"]["채널"] == "JTBC"
    assert "review" not in content["programs"][0]
