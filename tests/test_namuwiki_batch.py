from __future__ import annotations

from broadcast_web_crawler import namuwiki_batch
from broadcast_web_crawler.namuwiki_batch import extract_matching_document

SHOW = """<title>방송</title><h1>방송(드라마)</h1><h2>1. 개요</h2><p>소개</p><table>
<tr><td>장르</td><td>휴먼</td></tr><tr><td>채널</td><td>tvN</td></tr>
<tr><td>방송 횟수</td><td>12부작</td></tr>
<tr><td rowspan="2">제작진</td><td>연출</td><td>감독</td></tr>
<tr><td>극본</td><td>작가</td></tr></table>"""


def test_source_link_to_same_title_drama_is_used(monkeypatch) -> None:
    check = {"status": "exists", "final_url": "https://namu.wiki/w/방송"}
    original = '<h1>방송</h1><h2>개요</h2><a href="/w/방송(드라마)">드라마</a>'
    calls = []

    def fetch(url):
        calls.append(url)
        return SHOW, {"status": "exists", "final_url": url}

    monkeypatch.setattr(namuwiki_batch, "fetch_document", fetch)
    monkeypatch.setattr(namuwiki_batch.time, "sleep", lambda _: None)
    content, report = extract_matching_document("방송", original, check)
    assert len(calls) == 1
    assert content["directors"] == ["감독"]
    assert content["writers"] == ["작가"]
    assert content["content_type"] == "드라마"
    assert report["extraction_status"] == "collected"
    assert len(report["document_checks"]) == 2


def test_unrelated_drama_link_is_never_substituted(monkeypatch) -> None:
    original = '<h1>방송</h1><h2>개요</h2><a href="/w/다른작품(드라마)">드라마</a>'
    check = {"status": "exists", "final_url": "https://namu.wiki/w/방송"}
    monkeypatch.setattr(namuwiki_batch, "fetch_document", lambda _: (_ for _ in ()).throw(
        AssertionError("Unrelated document must not be fetched")
    ))
    content, report = extract_matching_document("방송", original, check)
    assert content is None
    assert report["extraction_status"] == "unsupported_document"
