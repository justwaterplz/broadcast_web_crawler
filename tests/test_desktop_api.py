import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from broadcast_web_crawler import desktop_api, tving

TOKEN = "desktop-test-token-with-sufficient-length"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_local_api_authentication_and_result_boundary(tmp_path):
    root = tmp_path / "data"
    app = desktop_api.create_desktop_app(root, TOKEN)
    run = root / "tving" / "run"
    run.mkdir(parents=True)
    result = run / "contents.json"
    result.write_text(
        json.dumps({"programs": [{"title": "작품", "episodes": []}]}), encoding="utf-8"
    )
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 401
        assert client.get("/health", headers=AUTH).status_code == 200
        items = client.get("/collections", headers=AUTH).json()
        assert items[0]["program_count"] == 1
        assert (
            client.post("/read", headers=AUTH, json={"path": str(result)}).json()["programs"][0][
                "title"
            ]
            == "작품"
        )
        assert client.post("/read", headers=AUTH, json={"path": str(outside)}).status_code == 400
        assert (
            client.post("/jobs", headers=AUTH, json={"url": "https://example.com/"}).status_code
            == 400
        )


def test_history_hide_persists_without_deleting_data_and_can_be_undone(tmp_path):
    root = tmp_path / "data"
    run = root / "tving" / "run"
    run.mkdir(parents=True)
    file = run / "contents.json"
    file.write_text('{"programs":[{"title":"작품"}]}', encoding="utf-8")
    before = file.read_bytes()
    with TestClient(desktop_api.create_desktop_app(root, TOKEN)) as client:
        assert client.post("/collections/hide", json={"path": str(file)}).status_code == 401
        response = client.post("/collections/hide", headers=AUTH, json={"path": str(file)})
        assert response.json()["data_preserved"] is True
        assert client.get("/collections", headers=AUTH).json() == []
        assert file.read_bytes() == before
        assert client.post("/read", headers=AUTH, json={"path": str(file)}).status_code == 200
    with TestClient(desktop_api.create_desktop_app(root, TOKEN)) as client:
        assert client.get("/collections", headers=AUTH).json() == []
        assert (
            client.post("/collections/restore", headers=AUTH, json={"path": str(file)}).json()[
                "hidden"
            ]
            is False
        )
        assert len(client.get("/collections", headers=AUTH).json()) == 1
        outside = tmp_path / "outside.json"
        outside.write_text("{}")
        assert (
            client.post("/collections/hide", headers=AUTH, json={"path": str(outside)}).status_code
            == 400
        )
        assert file.read_bytes() == before


def test_inventory_job_and_collection_share_the_saved_complete_snapshot(tmp_path, monkeypatch):
    root = tmp_path / "data"
    expected = {
        "format": "tving-category-inventory",
        "source_url": "https://www.tving.com/more/genre/PCA",
        "category": "drama",
        "subcategory": "전체",
        "checked_at": "2026-10-12T12:00:00+09:00",
        "unique_count": 1,
        "pages_read": 1,
        "complete_listing": True,
        "order": "hit",
        "duplicate_items_count": 0,
        "programs": [
            {
                "rank": 1,
                "title": "작품",
                "url": "https://www.tving.com/contents/P001",
            }
        ],
    }

    def scan(output, **kwargs):
        assert kwargs["url"] == expected["source_url"]
        file = output / "scan" / "inventory.json"
        file.parent.mkdir(parents=True)
        file.write_text(json.dumps(expected), encoding="utf-8")
        kwargs["on_progress"](expected)
        return expected, file

    received = []

    def collect(output, limit, **kwargs):
        received.append(kwargs["inventory"])
        run = output / "run"
        run.mkdir(parents=True)
        (run / "contents.json").write_text('{"programs":[{"title":"작품"}]}', encoding="utf-8")
        return {"output_dir": str(run), "summary": {"successful_programs": 1}}

    monkeypatch.setattr(desktop_api, "scan_inventory", scan)
    monkeypatch.setattr(desktop_api, "collect_top_programs", collect)
    with TestClient(desktop_api.create_desktop_app(root, TOKEN)) as client:
        assert (
            client.post("/inventory/jobs", json={"url": expected["source_url"]}).status_code == 401
        )
        response = client.post(
            "/inventory/jobs", headers=AUTH, json={"url": expected["source_url"]}
        )
        job_id = response.json()["id"]
        for _ in range(100):
            job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)
        assert job["status"] == "completed" and job["summary"]["complete"] is True
        saved = client.get("/inventories", headers=AUTH).json()[0]
        assert saved["unique_count"] == 1 and saved["file"] == job["inventory_file"]
        response = client.post(
            "/jobs",
            headers=AUTH,
            json={
                "url": expected["source_url"],
                "all_programs": True,
                "inventory_file": saved["file"],
            },
        )
        job_id = response.json()["id"]
        for _ in range(100):
            job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)
        assert job["status"] == "completed" and received == [expected]
        partial = {**expected, "complete_listing": False}
        Path(saved["file"]).write_text(json.dumps(partial), encoding="utf-8")
        assert (
            client.post(
                "/jobs",
                headers=AUTH,
                json={
                    "url": expected["source_url"],
                    "all_programs": True,
                    "inventory_file": saved["file"],
                },
            ).status_code
            == 400
        )


def test_url_job_routes_to_direct_wiki_and_saves_result(tmp_path, monkeypatch):
    root = tmp_path / "data"

    def collect(url, output):
        assert url == "https://namu.wiki/w/%EC%9E%91%ED%92%88"
        output.mkdir(parents=True, exist_ok=True)
        file = output / "contents.json"
        file.write_text('{"programs": [{"title": "작품"}]}', encoding="utf-8")
        return {"extraction_status": "collected", "content_file": str(file)}

    monkeypatch.setattr(desktop_api, "collect_document", collect)
    with TestClient(desktop_api.create_desktop_app(root, TOKEN)) as client:
        response = client.post("/jobs", headers=AUTH, json={"url": "https://namu.wiki/w/작품"})
        assert response.status_code == 202
        job_id = response.json()["id"]
        for _ in range(100):
            job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)
        assert job["status"] == "completed", job
        result = client.post("/read", headers=AUTH, json={"path": job["content_file"]}).json()
        assert result["programs"][0]["title"] == "작품"


def test_tving_detail_job_keeps_one_bundle_and_renders_original_json(tmp_path, monkeypatch):
    info = {
        "program_code": "P001",
        "title": "작품",
        "director": ["인명"],
        "extra": {"image": "poster.jpg", "value": False},
    }
    html = (
        '<script id="__NEXT_DATA__">'
        + json.dumps(
            {
                "props": {
                    "pageProps": {
                        "contentInfo": info,
                    }
                }
            }
        )
        + '</script><script src="/_next/static/chunks/pages/_app-test.js"></script>'
    )
    raw_api = '{"header":{"status":200},"body":{"result":[],"total_count":0,"has_more":"N"}}'

    def get(url):
        if "/contents/" in url:
            return html
        if "_app-" in url:
            return '46900:function(){var b="test-key"}'
        return raw_api

    monkeypatch.setattr(tving, "_get_text", get)
    with TestClient(desktop_api.create_desktop_app(tmp_path / "data", TOKEN)) as client:
        job_id = client.post(
            "/jobs", headers=AUTH, json={"url": "https://www.tving.com/contents/P001"}
        ).json()["id"]
        for _ in range(100):
            job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)
        assert job["status"] == "completed", job
        run = Path(job["content_file"]).parent
        report = json.loads((run / "collection-report.json").read_text(encoding="utf-8"))
        metadata_path = run / report["metadata_file"]
        bundle = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert bundle["contentInfo"] == info
        assert bundle["episodeApi"] == json.loads(raw_api)
        assert [p.name for p in metadata_path.parent.iterdir()] == ["metadata.json"]
        index = client.post("/read", headers=AUTH, json={"path": job["content_file"]}).json()
        assert "episodes" not in index["programs"][0]
        view = client.post("/view", headers=AUTH, json={"path": job["content_file"]}).json()
        assert view["source_documents"][0] == bundle
        assert view["programs"][0]["directors"] == ["인명"]
        lazy_view = client.post(
            "/view", headers=AUTH, json={"path": job["content_file"], "program_index": 0}
        ).json()
        assert lazy_view["source_documents"]["0"] == bundle
        assert lazy_view["programs"][0]["directors"] == ["인명"]
        assert client.get("/collections", headers=AUTH).json()[0]["title"] == "작품"
        # A reference may not escape this run, even to another file inside the output root.
        index["programs"][0]["metadata_file"] = "../outside.json"
        Path(job["content_file"]).write_text(json.dumps(index), encoding="utf-8")
        assert (
            client.post("/view", headers=AUTH, json={"path": job["content_file"]}).status_code
            == 400
        )
