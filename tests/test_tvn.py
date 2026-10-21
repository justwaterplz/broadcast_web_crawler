import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from fastapi.testclient import TestClient

from broadcast_web_crawler import desktop_api, tvn

TOKEN = "tvn-test-token-with-sufficient-length"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def row(code, title, genre="드라마"):
    return {"pgmSeq": code, "pgmNm": title, "repGenreInfo": genre,
            "ptclrGenreInfo": genre, "frontDetailUrlAddr": f"{tvn.ORIGIN}/ko/show-{code}/",
            "nullable": None, "unknown": {"image": "poster.jpg", "flag": False}}


def page_html(items):
    module = {"tmplModulSeq": 14382, "ajaxModulUrl": "/apis/v1/tmplModul/14382",
              "ajaxParams": {"pageNum": 1, "searchChnCd": "ALL", "repGenreCdList": "ALL"}}
    props = {"pageInfo": {}, "fallback": {
        "14382": {"data": {"dataInfo": {"list": items}}},
        "23366": {"data": None},
        "template": {"tempInfo": [module, {"tmplModulSeq": 23366}]},
    }}
    return '<script id="__NEXT_DATA__">' + json.dumps(
        {"props": {"pageProps": props}}
    ) + "</script>"


def listing_api(number, items, total, last):
    return json.dumps({"resultCd": "0000", "result": {"data": {"dataInfo": {
        "pageNum": number, "list": items, "total": total,
        "isLastPage": last, "hasNextPage": not last,
    }}}})


def detail_html(code=1):
    header = {"modulAttrInfo": {"pgmSeq": code}, "data": {
        "pgmNm": "작품", "plnngIntentInfo": {"plnngIntentSumryCnts": "소개"},
        "nullable": None, "unknown": {"image": "poster.jpg", "flag": False},
    }}
    characters = {"data": {"simplePrsnInfoList": [{"prsnNm": "등장인물"}]}}
    preview = {"data": {"previewInfoList": [{"pgmTmnoPrevewSeq": 7,
        "prevewTit": "2화 미리보기", "prevewCnts": "<p>회차 소개</p>"}]}}
    props = {"pageInfo": {"pageInfo": {"snsTitTagCnts": "작품", "repGenreInfo": "드라마"}},
             "fallback": {"10": header, "11": characters, "12": preview,
                          "template": {"tempInfo": [{"tmplModulSeq": 10}]}}}
    return '<script id="__NEXT_DATA__">' + json.dumps(
        {"props": {"pageProps": props}}
    ) + "</script>", props


def setup_http(monkeypatch):
    first = row(1, "작품", "예능")
    second = row(2, "드라마작품", "드라마")
    calls = []

    def get(url):
        calls.append(url)
        if "/ko/program/" in url:
            return page_html([first])
        if "/tmplModul/" in url:
            params = parse_qs(urlsplit(url).query)
            number = int(params["pageNum"][0])
            return listing_api(number, [first] if number == 1 else [first, second], 2,
                               number == 2)
        code = int(urlsplit(url).path.rstrip("/").rsplit("-", 1)[1])
        return detail_html(code)[0]

    monkeypatch.setattr(tvn, "_get_text", get)
    monkeypatch.setattr(tvn.time, "sleep", lambda _: None)
    return first, second, calls


def test_channel_filters_are_decoded_without_reclassifying_or_dropping_programs(monkeypatch):
    _, _, calls = setup_http(monkeypatch)
    url = tvn.LISTING_URL + "?" + urlencode({"14382":
        "pageNum=21&searchChnCd=MC010272&repGenreCdList=ALL"})
    listing = tvn.discover_programs(url)
    assert listing["channel_tab"] == "tvN SHOW"
    assert listing["complete_listing"] and listing["unique_count"] == 2
    assert listing["duplicate_items_count"] == 1
    assert [p["listing_item"]["repGenreInfo"] for p in listing["programs"]] == ["예능", "드라마"]
    queries = [parse_qs(urlsplit(u).query) for u in calls if "/tmplModul/" in u]
    assert [q["pageNum"] for q in queries] == [["1"], ["2"]]
    assert all(q["searchChnCd"] == ["MC010272"] for q in queries)


def test_page_cap_and_wrong_api_page_are_never_complete(tmp_path, monkeypatch):
    first, _, _ = setup_http(monkeypatch)
    report, file = tvn.scan_inventory(tmp_path, url=tvn.LISTING_URL, max_pages=1)
    assert report["unique_count"] == 1 and report["complete_listing"] is False
    assert "error" in report
    assert json.loads(file.read_text(encoding="utf8")) == report
    monkeypatch.setattr(tvn, "_get_text", lambda u: page_html([first]) if "/ko/" in u
                        else listing_api(1, [first], 2, False))
    with pytest.raises(tvn.TvnError, match="페이지 번호"):
        tvn.discover_programs(tvn.LISTING_URL)


def test_raw_modules_are_preserved_and_characters_are_not_cast(tmp_path, monkeypatch):
    html, props = detail_html()
    monkeypatch.setattr(tvn, "_get_text", lambda _: html)
    original = row(1, "예능작품", "예능")
    file = tmp_path / "metadata.json"
    bundle = tvn.collect_program(original["frontDetailUrlAddr"], file, listing_item=original)
    assert bundle["listingItem"] == original
    assert bundle["modules"]["10"] == props["fallback"]["10"]
    assert json.loads(file.read_text(encoding="utf8")) == bundle
    shown = tvn.display_content(bundle)
    assert shown["content_type"] == "예능" and shown["cast"] is None
    assert shown["characters"][0]["prsnNm"] == "등장인물"
    assert shown["episodes"][0]["number"] == 2
    assert shown["episodes"][0]["synopsis"] == "회차 소개"
    assert bundle["collection"]["complete_episode_list"] is False
    with pytest.raises(tvn.TvnError, match="ID"):
        tvn.collect_program(original["frontDetailUrlAddr"], file, listing_item=row(99, "다른작품"))


def test_saved_inventory_runs_keep_mixed_genres_and_partial_failures(tmp_path, monkeypatch):
    _, second, calls = setup_http(monkeypatch)
    inventory, _ = tvn.scan_inventory(tmp_path / "inventories", url=tvn.LISTING_URL)
    calls.clear()
    report = tvn.collect_programs(tmp_path / "tvn", limit=20, url=tvn.LISTING_URL,
                                  inventory=inventory)
    assert report["summary"]["successful_programs"] == 2
    assert all("/ko/show-" in url for url in calls)
    run = Path(report["output_dir"])
    index = json.loads((run / "contents.json").read_text(encoding="utf8"))
    assert len(index["programs"]) == 2 and index["format"] == tvn.INDEX_FORMAT
    genres = [tvn.display_content(json.loads((run / p["metadata_file"]).read_text(
        encoding="utf8")))["content_type"] for p in index["programs"]]
    assert genres == ["예능", "드라마"]
    original_get = tvn._get_text

    def fail_one(url):
        if url == second["frontDetailUrlAddr"]:
            raise tvn.TvnError("sample unavailable")
        return original_get(url)

    monkeypatch.setattr(tvn, "_get_text", fail_one)
    report = tvn.collect_programs(tmp_path / "tvn", url=tvn.LISTING_URL, inventory=inventory)
    assert report["summary"]["successful_programs"] == 1
    assert report["summary"]["failed_programs"] == 1
    assert report["programs"][1]["error"] == "sample unavailable"


@pytest.mark.parametrize("url", ["https://evil.test/ko/program/", "http://tvn.cjenm.com/ko/a/",
                                 "https://tvn.cjenm.com/ko/signin/",
                                 "https://tvn.cjenm.com.evil.test/ko/a/"])
def test_unsupported_origins_and_account_pages_are_rejected(url):
    with pytest.raises(ValueError):
        tvn.normalize_url(url)


def test_explicit_preview_menu_and_api_pages_preserve_raw_data(tmp_path, monkeypatch):
    root_html, original = detail_html(1)
    root_html += '<a href="/ko/show-1/episodes/">미리보기</a>'
    rows = [{"pgmTmnoPrevewSeq": n, "prevewTit": f"{n}화", "prevewCnts": "원본 설명",
             "unknown": [None, False, "001"]} for n in (7, 8, 9)]
    first = {"total": 3, "list": rows[:2], "pageNum": 1, "nextPage": 2,
             "isLastPage": False, "hasNextPage": True}
    second = {**first, "list": rows[2:], "pageNum": 2, "nextPage": 0,
              "isLastPage": True, "hasNextPage": False}
    props = {"pageInfo": {}, "fallback": {"20": {"modulAttrInfo": {"pgmSeq": 1},
                "data": {"dataInfo": first}}, "template": {"tempInfo": [{
                "tmplModulSeq": 20, "ajaxModulUrl": "/apis/v1/tmplModul/20",
                "ajaxParams": {"removeCacheYn": "N"}}]}}}
    html = '<script id="__NEXT_DATA__">' + json.dumps({"props": {"pageProps": props}}) + '</script>'
    api = {"resultCd": "0000", "result": {"data": {"dataInfo": second}}}
    calls = []

    def get(url):
        calls.append(url)
        if "/tmplModul/" in url:
            assert parse_qs(urlsplit(url).query)["pageNum"] == ["2"]
            return json.dumps(api)
        return html if url.endswith("/episodes/") else root_html

    monkeypatch.setattr(tvn, "_get_text", get)
    monkeypatch.setattr(tvn.time, "sleep", lambda _: None)
    path = tmp_path / "metadata.json"
    bundle = tvn.collect_program("https://tvn.cjenm.com/ko/show-1/", path)
    assert bundle["modules"]["12"] == original["fallback"]["12"]
    assert bundle["linkedPages"][0]["modules"]["20"]["data"]["dataInfo"] == first
    assert bundle["previewApiResponses"][0]["response"] == api
    assert bundle["collection"]["preview_listing"]["complete_for_current_preview_listing"] is True
    assert bundle["collection"]["complete_episode_list"] is False
    assert len(tvn.display_content(bundle)["episodes"]) == 3
    assert len(calls) == 3 and [p.name for p in tmp_path.iterdir()] == ["metadata.json"]


def wait_job(client, job_id):
    import time

    for _ in range(100):
        job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_desktop_inventory_collection_lazy_view_and_source_label(tmp_path, monkeypatch):
    setup_http(monkeypatch)
    with TestClient(desktop_api.create_desktop_app(tmp_path / "data", TOKEN)) as client:
        assert client.post("/inspect", headers=AUTH, json={"url": tvn.LISTING_URL}).json()[
            "kind"] == "tvn_category"
        submitted = client.post("/inventory/jobs", headers=AUTH, json={"url": tvn.LISTING_URL})
        scanned = wait_job(client, submitted.json()["id"])
        assert scanned["status"] == "completed", scanned
        saved = client.get("/inventories", headers=AUTH).json()[0]
        assert saved["category"] == "tvn" and saved["unique_count"] == 2
        submitted = client.post("/jobs", headers=AUTH, json={"url": tvn.LISTING_URL,
            "all_programs": True, "inventory_file": saved["file"]})
        job = wait_job(client, submitted.json()["id"])
        assert job["status"] == "completed", job
        items = client.get("/collections", headers=AUTH).json()
        assert items[0]["source"] == "tvN" and items[0]["program_count"] == 2
        view = client.post("/view", headers=AUTH, json={"path": job["content_file"],
                                                    "program_index": 1}).json()
        assert view["programs"][1]["content_type"] == "드라마"
        assert view["source_documents"]["1"]["listingItem"]["repGenreInfo"] == "드라마"
        index_path = Path(job["content_file"])
        index = json.loads(index_path.read_text(encoding="utf8"))
        index["programs"][0]["metadata_file"] = "../outside.json"
        index_path.write_text(json.dumps(index), encoding="utf8")
        assert client.post("/view", headers=AUTH, json={"path": job["content_file"],
                                                    "program_index": 0}).status_code == 400
        partial = json.loads(Path(saved["file"]).read_text(encoding="utf8"))
        partial["complete_listing"] = False
        Path(saved["file"]).write_text(json.dumps(partial), encoding="utf8")
        assert client.post("/jobs", headers=AUTH, json={"url": tvn.LISTING_URL,
            "inventory_file": saved["file"]}).status_code == 400
