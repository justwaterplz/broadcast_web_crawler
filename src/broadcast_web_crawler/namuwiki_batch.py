"""Resolve titles in a saved TVING collection to exact NamuWiki documents."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from broadcast_web_crawler.namuwiki import (
    WikiError,
    fetch_document,
    parse_document,
    resolve_document,
)
from broadcast_web_crawler.output_paths import KST, create_run_folder, safe_folder_name
from broadcast_web_crawler.source_records import save_source_record, wiki_source_record


def read_titles(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    programs = json.loads(path.read_text(encoding="utf-8"))["programs"]
    titles = []
    seen = set()
    for program in programs:
        title = program["title"].strip()
        if not title or title in seen:
            continue
        seen.add(title)
        titles.append({"title": title, "tving_program_id": program.get("program_id")})
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        titles = titles[:limit]
    if not titles:
        raise ValueError("Input contains no program titles")
    return titles


def extract_matching_document(
    title: str, html: str, check: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Try the exact article, then one explicitly linked same-title drama article."""
    item = {**check, "document_checks": [dict(check)]}
    try:
        content, evidence = parse_document(html, check["final_url"])
    except WikiError as exc:
        expected = "/w/" + title + "(드라마)"
        candidate = next((a["href"] for a in BeautifulSoup(html, "html.parser").find_all(
            "a", href=True
        ) if unquote(urlsplit(a["href"]).path) == expected
            and urlsplit(a["href"]).netloc in {"", "namu.wiki"}), None)
        if candidate is None:
            item.update(extraction_status="unsupported_document", error=str(exc))
            return None, item
        # Use only a same-title link actually found on the source page; do not guess URLs.
        candidate_url = resolve_document("https://namu.wiki" + expected)
        time.sleep(1)
        candidate_html, candidate_check = fetch_document(candidate_url)
        item["document_checks"].append(candidate_check)
        item["linked_drama_url"] = candidate_url
        if candidate_check["status"] != "exists":
            item.update(extraction_status="linked_document_unavailable")
            return None, item
        try:
            content, evidence = parse_document(candidate_html, candidate_check["final_url"])
        except WikiError as linked_exc:
            item.update(extraction_status="unsupported_document", error=str(linked_exc))
            return None, item
        item["metadata_source_url"] = candidate_check["final_url"]
    else:
        item["metadata_source_url"] = check["final_url"]
    item.update(evidence, extraction_status="collected", resolved_title=content["title"])
    return content, item


def collect_tving_titles(
    source: Path, output_root: Path, *, limit: int | None = None, save_raw: bool = False
) -> dict[str, Any]:
    titles = read_titles(source, limit)
    now = datetime.now(KST)
    output = create_run_folder(output_root, "나무위키", f"TVING_{len(titles)}개작품", now)
    contents: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "source_file": str(source.resolve()), "started_at": now.isoformat(),
        "matching_policy": "Exact title, then one explicitly linked same-title drama document",
        "output_dir": str(output.resolve()), "programs": [], "summary": {},
    }
    for entry in titles:
        folder = output / f"{safe_folder_name(entry['title'])}_{now:%Y%m%d}"
        suffix = 2
        while folder.exists():
            folder = output / f"{safe_folder_name(entry['title'])}_{now:%Y%m%d}_{suffix}"
            suffix += 1
        folder.mkdir()
        item: dict[str, Any] = {**entry, "folder": folder.name}
        try:
            html, check = fetch_document(entry["title"])
            item.update(check)
            if item["status"] == "exists":
                if save_raw:
                    (folder / "source.html").write_text(html, encoding="utf-8")
                content, extracted = extract_matching_document(entry["title"], html, check)
                item.update(extracted)
                if content is not None:
                    contents.append(content)
                    (folder / "program.json").write_text(
                        json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    snapshot = wiki_source_record(content, item)
                    save_source_record(folder / "source-record.json", snapshot)
                    item.update(source_record_file=str((folder / "source-record.json").resolve()),
                                review=snapshot["review"])
        except (WikiError, ValueError, KeyError, TypeError) as exc:
            item.update(status="error", error=str(exc))
        report["programs"].append(item)
        status_counts = Counter(row["status"] for row in report["programs"])
        report["summary"] = {
            "requested_titles": len(titles), "processed_titles": len(report["programs"]),
            "document_status_counts": dict(status_counts),
            "metadata_collected": len(contents),
            "existing_but_unsupported": sum(
                row.get("extraction_status") == "unsupported_document" for row in report["programs"]
            ),
        }
        (folder / "collection-report.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "contents.json").write_text(
            json.dumps({"programs": contents}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "collection-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({"title": entry["title"], "status": item["status"],
                          "extraction_status": item.get("extraction_status")},
                         ensure_ascii=False), flush=True)
        time.sleep(1)
    report["finished_at"] = datetime.now(KST).isoformat()
    (output / "collection-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Saved TVING contents.json")
    parser.add_argument("--output-dir", type=Path, default=Path("data/namuwiki"))
    parser.add_argument("--limit", type=int, help="Optional number of unique input titles")
    parser.add_argument("--save-raw", action="store_true", help="Keep source HTML for diagnostics")
    parser.add_argument("--allow-title-routing", action="store_true",
                        help="Opt into legacy experimental title routing; results need URL review")
    args = parser.parse_args()
    if not args.allow_title_routing:
        parser.error("Use reviewed document URLs with namuwiki, or explicitly opt into "
                     "experimental title routing with --allow-title-routing")
    report = collect_tving_titles(
        args.input, args.output_dir, limit=args.limit, save_raw=args.save_raw
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Saved JSON: {Path(report['output_dir']) / 'contents.json'}")


if __name__ == "__main__":
    main()
