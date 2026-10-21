import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from broadcast_web_crawler import cjenm, desktop_api, url_review

TOKEN = "official-url-review-test-token-20261020"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
CJ_URL = "https://www.cjenm.com/ko/featured-contents/작품/"


def test_direct_tving_url_is_previewed_without_title_search(monkeypatch):
    info = {"program_code": "P001", "title": "입력한 작품", "director": ["인명"]}
    html = '<script id="__NEXT_DATA__">' + json.dumps({"props": {"pageProps": {
        "contentInfo": info,
    }}}) + '</script>'
    calls = []
    def get(url):
        calls.append(url)
        return html
    monkeypatch.setattr(url_review, "_get_text", get)
    result = url_review.inspect_official_url("https://www.tving.com/contents/P001",
                                             "tving_detail", "drama")
    assert result["title"] == "입력한 작품"
    assert calls == ["https://www.tving.com/contents/P001"]
    with pytest.raises(ValueError, match="ID"):
        url_review.inspect_official_url("https://www.tving.com/contents/P002",
                                         "tving_detail", "drama")


def test_desktop_target_review_cannot_be_reused_for_another_url(tmp_path, monkeypatch):
    def preview(url, kind, category):
        return {"url": url, "kind": kind, "status": "ready", "title": "작품", "site": "TVING"}
    monkeypatch.setattr(desktop_api, "inspect_official_url", preview)
    with TestClient(desktop_api.create_desktop_app(tmp_path, TOKEN)) as client:
        url = "https://www.tving.com/contents/P001"
        reviewed = client.post("/inspect", headers=AUTH, json={"url": url}).json()
        request = {"url": url, "require_review": True, "review_id": reviewed["review_id"]}
        assert client.post("/jobs", headers=AUTH, json=request).status_code == 400
        request.update(confirmed_target=True, url="https://www.tving.com/contents/P002")
        assert client.post("/jobs", headers=AUTH, json=request).status_code == 400
        assert client.get("/jobs", headers=AUTH).json() == []


def test_cjenm_manual_import_preserves_raw_responses_and_requires_matching_review(tmp_path):
    program = {"resultCd": "0000", "result": {"data": {"pgmSeq": 123, "pgmNm": "작품",
               "unknown": [False, None, 0, "001"], "image": "poster.jpg"}}}
    characters = {"resultCd": "0000", "result": {"data": {
        "pgmSeq": 123, "detailPrsnInfoList": [], "original": "<p>설명</p>",
    }}}
    request = {"url": CJ_URL, "program_response": program, "characters_response": characters}
    with TestClient(desktop_api.create_desktop_app(tmp_path, TOKEN)) as client:
        policy = client.post("/inspect", headers=AUTH, json={"url": CJ_URL}).json()
        assert policy["status"] == "manual_import_required"
        assert client.post("/cjenm/import", headers=AUTH, json=request).status_code == 400
        inspection = client.post("/cjenm/inspect", headers=AUTH, json=request).json()
        request.update(review_id=inspection["review_id"], confirmed_target=True)
        result = client.post("/cjenm/import", headers=AUTH, json=request)
        assert result.status_code == 201, result.text
        content_file = result.json()["content_file"]
        index = json.loads(Path(content_file).read_text(encoding="utf-8"))
        path = Path(content_file).parent / index["programs"][0]["metadata_file"]
        bundle = json.loads(path.read_text(encoding="utf-8"))
        assert bundle["programResponse"] == program and bundle["charactersResponse"] == characters
        assert bundle["collection"]["network_requests"] == 0
        assert bundle["collection"]["source_binding"] == "user_confirmed"
        assert [p.name for p in path.parent.iterdir()] == ["metadata.json"]
        view = client.post("/view", headers=AUTH,
                           json={"path": content_file, "program_index": 0}).json()
        assert view["programs"][0]["title"] == "작품"
        assert client.get("/collections", headers=AUTH).json()[0]["source"] == "CJ ENM"
        request["program_response"] = {**program, "extra": "changed after review"}
        assert client.post("/cjenm/import", headers=AUTH, json=request).status_code == 400
    with pytest.raises(ValueError, match="확인"):
        cjenm.import_saved_responses(CJ_URL, program, tmp_path)


def test_cjenm_character_response_for_different_program_is_rejected():
    program = {"resultCd": "0000", "result": {"data": {"pgmNm": "작품", "pgmSeq": 1}}}
    characters = {"resultCd": "0000", "result": {"data": {"pgmSeq": 2}}}
    with pytest.raises(ValueError, match="ID"):
        cjenm.inspect_saved_responses(CJ_URL, program, characters)
