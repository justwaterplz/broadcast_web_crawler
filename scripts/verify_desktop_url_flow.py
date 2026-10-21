"""명시적으로 입력한 공식 URL로 웹앱의 확인·검수·저장 경로를 검증합니다."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from broadcast_web_crawler.desktop_api import create_desktop_app
from broadcast_web_crawler.output_paths import KST


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--cjenm-url")
    parser.add_argument("--program-response", type=Path)
    parser.add_argument("--characters-response", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    token = "local-code-path-verification-20261020"
    auth = {"Authorization": f"Bearer {token}"}
    report = {
        "checked_at": datetime.now(KST).isoformat(),
        "automatic_title_search": False,
        "confirmation_source": "automated test simulates the user checkbox",
        "results": [],
    }

    def check_saved(client, result):
        index_path = Path(result["content_file"])
        index = json.loads(index_path.read_text(encoding="utf-8"))
        path = index_path.parent / index["programs"][0]["metadata_file"]
        bundle = json.loads(path.read_text(encoding="utf-8"))
        assert bundle["collection"]["target_review"]
        assert [p.name for p in path.parent.iterdir()] == ["metadata.json"]
        view = client.post("/view", headers=auth,
                           json={"path": str(index_path), "program_index": 0})
        view.raise_for_status()
        return bundle, {"metadata_file": str(path), "single_program_json": True,
                        "review_persisted": True,
                        "title": view.json()["programs"][0]["title"],
                        "status": "passed"}

    with TestClient(create_desktop_app(root / "app-data", token)) as client:
        for url in args.url:
            preview = client.post("/inspect", headers=auth, json={"url": url})
            preview.raise_for_status()
            inspected = preview.json()
            assert inspected["status"] == "ready", inspected
            request = {"url": inspected["url"], "require_review": True,
                       "review_id": inspected["review_id"]}
            assert client.post("/jobs", headers=auth, json=request).status_code == 400
            submitted = client.post("/jobs", headers=auth,
                                    json={**request, "confirmed_target": True})
            submitted.raise_for_status()
            job = submitted.json()
            deadline = time.monotonic() + 90
            while job["status"] not in {"completed", "failed"}:
                assert time.monotonic() < deadline, job
                time.sleep(0.25)
                job = client.get(f"/jobs/{job['id']}", headers=auth).json()
            assert job["status"] == "completed", job
            bundle, row = check_saved(client, job)
            row.update(url=url, unconfirmed_request_rejected=True,
                       preview_title=inspected["title"], kind=inspected["kind"],
                       collection=bundle["collection"])
            report["results"].append(row)
        if args.program_response:
            program = json.loads(args.program_response.read_text(encoding="utf-8-sig"))
            people = (json.loads(args.characters_response.read_text(encoding="utf-8-sig"))
                      if args.characters_response else None)
            request = {"url": args.cjenm_url, "program_response": program,
                       "characters_response": people}
            preview = client.post("/cjenm/inspect", headers=auth, json=request)
            preview.raise_for_status()
            assert client.post("/cjenm/import", headers=auth, json=request).status_code == 400
            imported = client.post("/cjenm/import", headers=auth, json={**request,
                                   "review_id": preview.json()["review_id"],
                                   "confirmed_target": True})
            imported.raise_for_status()
            bundle, row = check_saved(client, imported.json())
            assert bundle["programResponse"] == program
            if people is not None:
                assert bundle["charactersResponse"] == people
            assert bundle["collection"]["network_requests"] == 0
            row.update(url=args.cjenm_url, kind="cjenm_import", raw_values_unchanged=True,
                       network_requests=0, unconfirmed_request_rejected=True)
            report["results"].append(row)
    (root / "contract-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
