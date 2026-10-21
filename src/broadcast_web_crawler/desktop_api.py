"""Authenticated local API used by the Electron desktop client."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import cjenm, tvn
from .comparison import compare_sources, save_comparison
from .namuwiki import check_document, collect_document, resolve_document
from .output_paths import KST, create_run_folder, safe_folder_name
from .tving import collect_program_with_report, content_metadata, normalize_content_url
from .tving_batch import _category_url, collect_top_programs
from .tving_inventory import INVENTORY_FORMAT, scan_inventory, validate_inventory
from .tving_storage import (
    BUNDLE_FILENAME,
    BUNDLE_FORMAT,
    INDEX_FORMAT,
    display_content,
    index_entry,
)
from .url_review import inspect_official_url


class SubmitCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=10, max_length=2048)
    category: Literal["drama", "entertainment"] = "drama"
    limit: int = Field(default=20, ge=1, le=1000)
    start_rank: int = Field(default=1, ge=1, le=100000)
    all_programs: bool = False
    max_pages: int = Field(default=500, ge=1, le=500)
    inventory_file: str | None = Field(default=None, max_length=2048)
    require_review: bool = False
    review_id: str | None = None
    confirmed_target: bool = False


class CjenmResponses(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    program_response: dict[str, Any]
    characters_response: dict[str, Any] | None = None
    review_id: str | None = None
    confirmed_target: bool = False


class SubmitComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=250)
    record_paths: list[str] = Field(min_length=2, max_length=10)
    confirmed_same_program: Literal[True]


class ViewCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    program_index: int | None = Field(default=None, ge=0, le=100000)


def route_url(url: str) -> tuple[str, str]:
    parts = urlsplit(url.strip())
    if parts.scheme != "https":
        raise ValueError("HTTPS URL을 입력해 주세요.")
    if parts.netloc.lower() in {"www.cjenm.com", "cjenm.com"}:
        return "cjenm_detail", cjenm.normalize_url(url)
    if parts.netloc.lower() == "tvn.cjenm.com":
        normalized = tvn.normalize_url(url)
        return ("tvn_category" if tvn.is_listing(normalized) else "tvn_detail"), normalized
    if parts.netloc.lower() == "namu.wiki":
        return "namuwiki", resolve_document(url)
    if parts.netloc.lower() in {"tving.com", "www.tving.com"}:
        if parts.path.startswith("/contents/"):
            return "tving_detail", normalize_content_url(url)[0]
        return "tving_category", _category_url(url)
    raise ValueError("TVING·tvN 프로그램 URL 또는 나무위키 /w/ 문서 URL을 입력해 주세요.")


def create_desktop_app(output_root: Path, token: str) -> FastAPI:
    if len(token) < 24:
        raise ValueError("Desktop API requires a strong per-session token")
    root = output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    jobs: dict[str, dict[str, Any]] = {}
    reviews: dict[str, dict[str, Any]] = {}
    lock = threading.Lock()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="metadata-collector")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Broadcast Metadata Studio", lifespan=lifespan)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied, f"Bearer {token}"):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

    def safe_json(path: str) -> Path:
        candidate = Path(path).resolve()
        if not candidate.is_relative_to(root) or candidate.suffix != ".json":
            raise HTTPException(400, "결과 저장 폴더 내 JSON만 열 수 있습니다.")
        if not candidate.is_file():
            raise HTTPException(404, "결과 파일을 찾을 수 없습니다.")
        return candidate

    def update(job_id: str, **values: Any) -> None:
        with lock:
            jobs[job_id].update(values)

    def register_review(result: dict[str, Any], fingerprint: str | None = None) -> dict[str, Any]:
        identifier = str(uuid4())
        with lock:
            if len(reviews) >= 100:
                reviews.pop(next(iter(reviews)))
            reviews[identifier] = {**result, "response_fingerprint": fingerprint}
        return {**result, "review_id": identifier}

    def confirm_review(identifier: str | None, confirmed: bool, url: str, kind: str,
                       fingerprint: str | None = None) -> dict[str, Any]:
        with lock:
            review = reviews.get(identifier or "")
        if (not confirmed or not review or review["url"] != url or review["kind"] != kind
                or review.get("response_fingerprint") != fingerprint):
            raise HTTPException(400, "URL 확인 후 사이트·작품 또는 목록이 맞는지 체크해 주세요.")
        return {k: v for k, v in review.items() if k != "response_fingerprint"} | {
            "confirmed_target": True, "confirmed_at": datetime.now(KST).isoformat()}

    def response_fingerprint(request: CjenmResponses) -> str:
        return hashlib.sha256(json.dumps([request.program_response, request.characters_response],
                                         sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def collect(job_id: str, request: SubmitCollection, kind: str, url: str) -> None:
        update(job_id, status="running", stage="페이지에 접속하고 있습니다.")
        try:
            if kind in {"tving_inventory", "tvn_inventory"}:
                def inventory_progress(value: dict[str, Any]) -> None:
                    update(job_id, stage=f"목록 {value['pages_read']}페이지 · "
                           f"{value['unique_count']:,}개 작품 확인", pages_read=value["pages_read"],
                           unique_count=value["unique_count"])

                if kind == "tvn_inventory":
                    inventory, inventory_path = tvn.scan_inventory(
                        root / "tvn-inventories", url=url, max_pages=request.max_pages,
                        on_progress=inventory_progress,
                    )
                else:
                    inventory, inventory_path = scan_inventory(
                        root / "tving-inventories", url=url, category=request.category,
                        max_pages=request.max_pages, on_progress=inventory_progress,
                    )
                update(job_id, status="completed", inventory_file=str(inventory_path.resolve()),
                       stage="전체 목록 확인 완료" if inventory["complete_listing"]
                       else "목록 일부 확인 · 전체 작품 수 미확정",
                       summary={"programs": inventory["unique_count"],
                                "complete": inventory["complete_listing"]},
                       finished_at=datetime.now(KST).isoformat())
                return
            if kind == "namuwiki":
                report = collect_document(url, root / "namuwiki")
                if report.get("extraction_status") != "collected":
                    status_messages = {
                        "not_found": "입력한 URL의 문서가 존재하지 않습니다.",
                        "access_denied": "사이트가 접근을 제한했습니다.",
                        "unknown": "문서 본문인지 확인할 수 없습니다.",
                        "network_error": "사이트에 연결하지 못했습니다.",
                    }
                    fallback = report.get("error", "방송 메타데이터를 추출하지 못했습니다.")
                    raise RuntimeError(status_messages.get(report["status"], fallback))
                content_file = report["content_file"]
                summary = {"programs": 1, "source": "나무위키"}
            elif kind in {"tvn_category", "tvn_detail"}:
                def tvn_progress(value: dict[str, Any]) -> None:
                    if "pages_read" in value:
                        update(job_id, stage=f"목록 {value['pages_read']}페이지 · "
                               f"{value['unique_count']:,}개 작품 확인")
                    else:
                        message = "수집 완료" if value["status"] == "success" else "수집 실패"
                        update(job_id, processed=value["processed"], total=value["total"],
                               stage=f"{value['title']} {message}",
                               content_file=value["content_file"])

                inventory_path = (safe_json(request.inventory_file)
                                  if request.inventory_file else None)
                inventory = (json.loads(inventory_path.read_text(encoding="utf-8"))
                             if inventory_path else None)
                report = tvn.collect_programs(
                    root / "tvn", None if request.all_programs else request.limit, url=url,
                    start_rank=request.start_rank, max_pages=request.max_pages,
                    inventory=inventory, on_progress=tvn_progress,
                )
                content_file = str(Path(report["output_dir"]) / "contents.json")
                summary = report["summary"]
                if summary["successful_programs"] == 0:
                    raise RuntimeError(
                        "tvN 메타데이터를 수집한 작품이 없습니다. 보고서를 확인해 주세요."
                    )
            elif kind == "tving_detail":
                now = datetime.now(KST)
                run = create_run_folder(root / "tving", "TVING", "작품상세", now)
                # Collect into the run, then use the resolved original title for the show folder.
                captured = collect_program_with_report(url, run)
                content = content_metadata(captured)
                show = run / f"{safe_folder_name(content['title'])}_{now:%Y%m%d}"
                show.mkdir()
                (run / BUNDLE_FILENAME).rename(show / BUNDLE_FILENAME)
                captured_report = run / "collection-report.json"
                relative = (show.relative_to(run) / BUNDLE_FILENAME).as_posix()
                diagnostics = {**captured["bundle"]["collection"], "metadata_file": relative}
                captured_report.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
                content_path = run / "contents.json"
                content_path.write_text(json.dumps({"format": INDEX_FORMAT, "schema_version": 1,
                    "programs": [index_entry(captured["bundle"], relative)]},
                    ensure_ascii=False, indent=2), encoding="utf-8")
                content_file = str(content_path.resolve())
                episodes = captured["episode_list"]
                summary = {"programs": 1, "episodes": episodes["collected_count"],
                           "complete": episodes["complete_for_current_api_listing"]}
            else:
                def progress(value: dict[str, Any]) -> None:
                    update(job_id, processed=value["processed"], total=value["total"],
                           stage=f"{value['title']} 수집 완료", content_file=value["content_file"])

                inventory_path = (safe_json(request.inventory_file)
                                  if request.inventory_file else None)
                inventory = (json.loads(inventory_path.read_text(encoding="utf-8"))
                             if inventory_path else None)
                report = collect_top_programs(
                    root / "tving", None if request.all_programs else request.limit,
                    start_rank=request.start_rank, category=request.category, url=url,
                    max_pages=request.max_pages, on_progress=progress,
                    inventory=inventory,
                )
                content_file = str(Path(report["output_dir"]) / "contents.json")
                summary = report["summary"]
                if summary["successful_programs"] == 0:
                    raise RuntimeError(
                        "방송 메타데이터를 수집한 작품이 없습니다. 보고서를 확인해 주세요."
                    )
            target_review = jobs[job_id].get("target_review")
            if target_review:
                index_path = Path(content_file)
                index_data = json.loads(index_path.read_text(encoding="utf-8"))
                for entry in index_data.get("programs", []):
                    if "metadata_file" not in entry:
                        continue
                    metadata_path = safe_json(str(index_path.parent / entry["metadata_file"]))
                    bundle = json.loads(metadata_path.read_text(encoding="utf-8"))
                    bundle["collection"]["target_review"] = target_review
                    from .tving_storage import write_bundle
                    write_bundle(metadata_path, bundle)
                report_path = index_path.parent / "collection-report.json"
                if report_path.exists():
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    report["target_review"] = target_review
                    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
            update(job_id, status="completed", stage="JSON 저장 완료", content_file=content_file,
                   summary=summary, finished_at=datetime.now(KST).isoformat())
        except Exception as exc:
            update(job_id, status="failed", stage="수집을 완료하지 못했습니다.", error=str(exc),
                   finished_at=datetime.now(KST).isoformat())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "output_root": str(root)}

    @app.post("/inspect")
    def inspect(request: SubmitCollection) -> dict[str, Any]:
        try:
            kind, url = route_url(request.url)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if kind == "namuwiki":
            return {"kind": kind, **check_document(url)}
        if kind == "cjenm_detail":
            return {"kind": kind, "status": "manual_import_required", "url": url,
                    "site": "CJ ENM",
                    "message": "공식 URL에 대응하는 저장된 API 응답을 선택해 주세요."}
        try:
            return register_review(inspect_official_url(url, kind, request.category))
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            raise HTTPException(400, "입력한 공식 URL을 확인하지 못했습니다: " + str(exc)) from exc

    @app.post("/cjenm/inspect")
    def inspect_cjenm(request: CjenmResponses) -> dict[str, Any]:
        try:
            result = cjenm.inspect_saved_responses(request.url, request.program_response,
                                                  request.characters_response)
            return register_review(result, response_fingerprint(request))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/cjenm/import", status_code=201)
    def import_cjenm(request: CjenmResponses) -> dict[str, Any]:
        try:
            url = cjenm.normalize_url(request.url)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        review = confirm_review(request.review_id, request.confirmed_target, url, "cjenm_detail",
                                response_fingerprint(request))
        report = cjenm.import_saved_responses(
            url, request.program_response, root / "cjenm", characters=request.characters_response,
            confirmed_target=True, review=review,
        )
        return {"id": str(uuid4()), "kind": "cjenm_import", "status": "completed",
                "stage": "CJ ENM 원본 응답 저장 완료", "summary": report["summary"],
                "content_file": str(Path(report["output_dir"]) / "contents.json")}

    def enqueue(request: SubmitCollection, kind: str, url: str) -> dict[str, Any]:
        target_review = (confirm_review(request.review_id, request.confirmed_target, url,
                         "tvn_category" if kind == "tvn_inventory" else
                         "tving_category" if kind == "tving_inventory" else kind)
                         if request.require_review else None)
        job_id = str(uuid4())
        with lock:
            if any(job["status"] in {"queued", "running"} for job in jobs.values()):
                raise HTTPException(409, "진행 중인 수집이 완료된 후 다시 시작해 주세요.")
            jobs[job_id] = {"id": job_id, "url": url, "kind": kind, "status": "queued",
                            "stage": "수집 준비 중", "started_at": datetime.now(KST).isoformat(),
                            "target_review": target_review}
            initial = dict(jobs[job_id])
        executor.submit(collect, job_id, request, kind, url)
        return initial

    @app.post("/jobs", status_code=202)
    def submit(request: SubmitCollection) -> dict[str, Any]:
        try:
            kind, url = route_url(request.url)
            if kind == "cjenm_detail":
                raise ValueError("CJ ENM은 저장된 응답 가져오기를 사용해 주세요.")
            if request.inventory_file:
                if kind not in {"tving_category", "tvn_category"}:
                    raise ValueError("저장한 목록은 TVING·tvN 목록 수집에만 사용할 수 있습니다.")
                inventory_path = safe_json(request.inventory_file)
                inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
                if kind == "tvn_category":
                    tvn.validate_inventory(inventory, url=url)
                else:
                    validate_inventory(inventory, url=url, category=request.category)
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc
        return enqueue(request, kind, url)

    @app.post("/inventory/jobs", status_code=202)
    def submit_inventory(request: SubmitCollection) -> dict[str, Any]:
        try:
            kind, url = route_url(request.url)
            if kind not in {"tving_category", "tvn_category"}:
                raise ValueError("TVING·tvN 목록 URL을 입력해 주세요.")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return enqueue(request, "tvn_inventory" if kind == "tvn_category"
                       else "tving_inventory", url)

    @app.get("/inventories")
    def inventories() -> list[dict[str, Any]]:
        results = []
        paths = sorted([*(root / "tving-inventories").glob("*/inventory.json"),
                        *(root / "tvn-inventories").glob("*/inventory.json")],
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for path in paths[:50]:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("format") in {INVENTORY_FORMAT, tvn.INVENTORY_FORMAT}:
                results.append({key: data.get(key) for key in (
                    "source_url", "category", "checked_at", "unique_count", "pages_read",
                    "complete_listing", "duplicate_items_count", "error", "channel_tab",
                )} | {"file": str(path.resolve())})
        return results

    @app.get("/jobs")
    def list_jobs() -> list[dict[str, Any]]:
        with lock:
            return [dict(job) for job in jobs.values()]

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        with lock:
            if job_id not in jobs:
                raise HTTPException(404, "수집 작업을 찾을 수 없습니다.")
            return dict(jobs[job_id])

    @app.get("/collections")
    def collections() -> list[dict[str, Any]]:
        results = []
        hidden = hidden_history()
        paths = sorted(root.glob("**/contents.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        # Include older TVING snapshots whose filename predates contents.json.
        paths += sorted(root.glob("**/drama-top20.json"))
        for path in paths:
            try:
                if path.resolve().relative_to(root).as_posix() in hidden:
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                programs = data.get("programs", [])
                if not programs or "title" not in programs[0]:
                    continue
                results.append({
                    "file": str(path.resolve()), "name": path.parent.name,
                    "title": programs[0]["title"], "program_count": len(programs),
                    "episode_count": sum(len(p.get("episodes", [])) for p in programs)
                    if data.get("format") not in {
                        INDEX_FORMAT, tvn.INDEX_FORMAT, cjenm.INDEX_FORMAT}
                    else None,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime, KST).isoformat(),
                    "source": ("나무위키" if "namuwiki" in path.parts else
                               "CJ ENM" if data.get("format") == cjenm.INDEX_FORMAT else
                               "tvN" if data.get("format") == tvn.INDEX_FORMAT else "TVING"),
                })
                if len(results) >= 100:
                    break
            except (ValueError, OSError, KeyError, TypeError):
                continue
        return results

    history_path = root / ".desktop" / "history-hidden.json"

    def hidden_history() -> set[str]:
        if not history_path.exists():
            return set()
        return set(json.loads(history_path.read_text(encoding="utf-8"))["hidden_files"])

    def change_history(payload: dict[str, str], hide: bool) -> dict[str, Any]:
        path = safe_json(payload.get("path", ""))
        if path.name not in {"contents.json", "drama-top20.json"}:
            raise HTTPException(400, "수집 결과 목록 파일을 지정해 주세요.")
        relative = path.relative_to(root).as_posix()
        with lock:
            hidden = hidden_history()
            if hide:
                hidden.add(relative)
            else:
                hidden.discard(relative)
            history_path.parent.mkdir(exist_ok=True)
            temporary = history_path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"hidden_files": sorted(hidden)}, ensure_ascii=False,
                                            indent=2), encoding="utf-8")
            temporary.replace(history_path)
        return {"file": str(path), "hidden": hide, "data_preserved": True}

    @app.post("/collections/hide")
    def hide_history(payload: dict[str, str]) -> dict[str, Any]:
        return change_history(payload, True)

    @app.post("/collections/restore")
    def restore_history(payload: dict[str, str]) -> dict[str, Any]:
        return change_history(payload, False)

    @app.post("/read")
    def read_file(payload: dict[str, str]) -> dict[str, Any]:
        return json.loads(safe_json(payload.get("path", "")).read_text(encoding="utf-8"))

    def display_source(document: dict[str, Any]) -> dict[str, Any]:
        if document.get("format") == cjenm.BUNDLE_FORMAT:
            return cjenm.parse_saved_responses(document["programResponse"],
                                                document.get("charactersResponse"))
        if document.get("format") == tvn.BUNDLE_FORMAT:
            return tvn.display_content(document)
        return display_content(document)

    @app.post("/view")
    def view_file(payload: ViewCollection) -> dict[str, Any]:
        """Render source bundles in memory while /read returns the saved JSON unchanged."""
        path = safe_json(payload.path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") in {BUNDLE_FORMAT, tvn.BUNDLE_FORMAT, cjenm.BUNDLE_FORMAT}:
            documents = [data]
        elif data.get("format") in {INDEX_FORMAT, tvn.INDEX_FORMAT, cjenm.INDEX_FORMAT}:
            if payload.program_index is not None:
                index = payload.program_index
                if index >= len(data["programs"]):
                    raise HTTPException(400, "작품 선택 범위를 확인해 주세요.")
                entry = data["programs"][index]
                candidate = (path.parent / entry["metadata_file"]).resolve()
                if not candidate.is_relative_to(path.parent):
                    raise HTTPException(400, "작품 원본은 해당 수집 폴더 안에 있어야 합니다.")
                source_path = safe_json(str(candidate))
                doc = json.loads(source_path.read_text(encoding="utf-8"))
                programs = [{"title": item["title"]} for item in data["programs"]]
                programs[index] = display_source(doc)
                return {"programs": programs, "source_documents": {str(index): doc}}
            documents = []
            for entry in data["programs"]:
                candidate = (path.parent / entry["metadata_file"]).resolve()
                if not candidate.is_relative_to(path.parent):
                    raise HTTPException(400, "작품 원본은 해당 수집 폴더 안에 있어야 합니다.")
                source_path = safe_json(str(candidate))
                documents.append(json.loads(source_path.read_text(encoding="utf-8")))
        else:
            return data
        try:
            return {"programs": [display_source(doc) for doc in documents],
                    "source_documents": documents}
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, "수집 원본 형식을 확인해 주세요.") from exc

    @app.post("/compare", status_code=201)
    def compare(request: SubmitComparison) -> dict[str, Any]:
        paths = [safe_json(value) for value in request.record_paths]
        try:
            records = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
            result = compare_sources(records, title=request.title,
                                     confirmed_same_program=request.confirmed_same_program)
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, "출처 기록을 확인해 주세요: " + str(exc)) from exc
        output = save_comparison(result, root / "comparisons")
        return {"comparison_file": str(output.resolve()), "comparison": result}

    return app


def main() -> None:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    args = parser.parse_args()
    token = os.environ.get("BROADCAST_DESKTOP_TOKEN", "")
    uvicorn.run(create_desktop_app(args.output_root, token), host="127.0.0.1", port=args.port,
                log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
