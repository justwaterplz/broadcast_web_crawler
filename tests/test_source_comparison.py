import json

import pytest
from fastapi.testclient import TestClient

from broadcast_web_crawler.cjenm import parse_saved_responses
from broadcast_web_crawler.comparison import compare_sources, load_manifest
from broadcast_web_crawler.desktop_api import create_desktop_app
from broadcast_web_crawler.source_records import source_record
from broadcast_web_crawler.tving import content_metadata

TOKEN = "comparison-test-token-with-sufficient-length"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def snapshot(source, content, url=None):
    return source_record(content, source=source, collected_at="2026-10-12T12:00:00+09:00",
                         method="saved_source_import", url=url or {
                             "tving": "https://www.tving.com/contents/P001",
                             "namuwiki": "https://namu.wiki/w/작품",
                             "cjenm": "https://www.cjenm.com/ko/featured-contents/작품/",
                         }[source])


def test_wiki_values_and_differences_stay_reviewable_without_overwriting():
    original = {"title": "작품", "genre": "드라마", "cast": ["배우1"], "episodes": []}
    official = snapshot("tving", original)
    wiki = snapshot("namuwiki", {"title": "작품", "genre": "음악, 청춘",
                                 "cast": ["배우1", "배우2"], "production_company": "제작사"})
    result = compare_sources([official, wiki], title="작품", confirmed_same_program=True)
    assert result["fields"]["title"]["status"] == "same_value"
    assert result["fields"]["genre"]["status"] == "different_values"
    assert result["fields"]["production_company"]["status"] == "single_source"
    assert wiki["review"]["status"] == "pending"
    assert all(c["review_status"] == "unreviewed"
               for f in result["fields"].values() for c in f["claims"])
    result["sources"][0]["content"]["cast"].append("edited")
    assert original["cast"] == official["content"]["cast"] == ["배우1"]


def test_identity_and_duplicate_documents_cannot_be_implicitly_accepted():
    record = snapshot("tving", {"title": "작품"})
    with pytest.raises(ValueError, match="Confirm"):
        compare_sources([record, record], title="작품", confirmed_same_program=False)
    with pytest.raises(ValueError, match="Duplicate"):
        compare_sources([record, record], title="작품", confirmed_same_program=True)


def test_changed_source_claim_is_rejected_instead_of_reusing_old_provenance():
    record = snapshot("namuwiki", {"title": "작품", "genre": "드라마"})
    record["content"]["genre"] = "변경된 주장"
    with pytest.raises(ValueError, match="changed"):
        compare_sources([record, snapshot("tving", {"title": "작품"})],
                        title="작품", confirmed_same_program=True)


def test_tving_mixed_credit_roles_are_not_invented():
    content = content_metadata({"detail": {"content_info": {
        "program_code": "P001", "title": "작품", "director": ["연출자", "작가"],
    }}, "episode_list": {"episodes": []}})
    assert content["directors"] == ["연출자", "작가"]
    assert "production_credits" not in content
    assert snapshot("tving", content)["review"]["flags"] == []


def test_saved_cjenm_response_is_parsed_without_invented_episode_details():
    program = {"resultCd": "0000", "result": {"data": {
        "pgmSeq": 123, "pgmNm": "작품", "writrNm": "작가", "allEpino": "12",
        "playrsNm": "배우1, 배우2", "dlbrtGrd": "15세 이상", "videoList": ["ignored"],
    }}}
    people = {"resultCd": "0000", "result": {"data": {"detailPrsnInfoList": [{
        "pgmPrsnIntrcnInfoList": [{"pgmPrsnSeq": 1, "prsnNm": "인물 (배우1)",
                                  "dtlDescpCnts": "인물 설명", "prsnImgFilePathAddr": "x.jpg"}],
    }]}}}
    content = parse_saved_responses(program, people)
    assert content["writers"] == ["작가"]
    assert content["episode_count"] == 12 and content["episodes"] == []
    assert content["characters"][0]["description"] == "인물 설명"
    assert "x.jpg" not in json.dumps(content)
    with pytest.raises(ValueError, match="successful"):
        parse_saved_responses({"resultCd": "error"})


def test_manifest_retains_legacy_credit_values_and_requires_explicit_selection(tmp_path):
    content = tmp_path / "contents.json"
    content.write_text(json.dumps({"programs": [{"title": "작품", "program_id": "P001",
                                                  "directors": ["연출자", "작가"]}]}))
    manifest = {"title": "작품", "confirmed_same_program": True, "sources": [{
        "source": "tving", "source_url": "https://www.tving.com/contents/P001",
        "collected_at": "2026-10-12T12:00:00+09:00", "content_file": "contents.json",
        "program_id": "P001", "acquisition_method": "saved_collection_import",
    }]}
    file = tmp_path / "manifest.json"
    file.write_text(json.dumps(manifest), encoding="utf-8")
    _, records = load_manifest(file)
    assert records[0]["content"]["directors"] == ["연출자", "작가"]
    assert "production_credits" not in records[0]["content"]
    assert records[0]["evidence"]["saved_content"]["directors"] == ["연출자", "작가"]
    manifest["sources"][0]["program_id"] = "other"
    file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="exactly one"):
        load_manifest(file)


def test_comparison_api_requires_authentication_confirmation_and_local_records(tmp_path):
    paths = []
    for source in ["tving", "namuwiki"]:
        file = tmp_path / f"{source}.json"
        file.write_text(json.dumps(snapshot(source, {"title": "작품", "episodes": []})),
                        encoding="utf-8")
        paths.append(str(file))
    with TestClient(create_desktop_app(tmp_path, TOKEN)) as client:
        payload = {"title": "작품", "record_paths": paths, "confirmed_same_program": True}
        assert client.post("/compare", json=payload).status_code == 401
        assert client.post("/compare", headers=AUTH,
                           json={**payload, "confirmed_same_program": False}).status_code == 422
        response = client.post("/compare", headers=AUTH, json=payload)
        assert response.status_code == 201, response.text
        result = client.post("/read", headers=AUTH,
                             json={"path": response.json()["comparison_file"]}).json()
        assert result["fields"]["title"]["status"] == "same_value"
        assert result["sources"][1]["review"]["status"] == "pending"
        assert client.post("/compare", headers=AUTH, json={**payload, "record_paths": [
            paths[0], str(tmp_path.parent / "outside.json"),
        ]}).status_code == 400
