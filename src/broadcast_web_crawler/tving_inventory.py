"""Checkpoint a TVING category inventory before collecting individual metadata."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .output_paths import KST, create_run_folder
from .tving import TvingError, normalize_content_url
from .tving_batch import CATEGORIES, _category_url, category_name, discover_programs
from .tving_storage import write_bundle

INVENTORY_FORMAT = "tving-category-inventory"


def validate_inventory(inventory: dict, *, url: str, category: str) -> None:
    if (
        inventory.get("format") != INVENTORY_FORMAT
        or inventory.get("source_url") != url
        or inventory.get("category") != category
        or inventory.get("complete_listing") is not True
    ):
        raise ValueError("완료된 동일 카테고리의 전체 목록을 사용해 주세요.")
    entries = inventory.get("programs")
    if not isinstance(entries, list) or not entries:
        raise ValueError("목록에 수집할 작품이 없습니다.")
    seen = set()
    for i, entry in enumerate(entries, 1):
        normalized, code = normalize_content_url(entry["url"])
        if (
            not code.startswith("P")
            or entry["url"] != normalized
            or code in seen
            or entry["rank"] != i
            or not isinstance(entry["title"], str)
        ):
            raise ValueError("작품 목록의 URL, 순서 또는 중복 항목을 확인해 주세요.")
        seen.add(code)
    if inventory.get("unique_count") != len(entries):
        raise ValueError("목록의 작품 수가 일치하지 않습니다.")


def scan_inventory(
    output_root: Path,
    *,
    url: str,
    category: str = "drama",
    max_pages: int = 500,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], Path]:
    if category not in CATEGORIES or max_pages < 1:
        raise ValueError("카테고리와 목록 페이지 상한을 확인해 주세요.")
    url = _category_url(url)
    subcategory = category_name(category, url)
    now = datetime.now(KST)
    output = create_run_folder(output_root, CATEGORIES[category]["name"], subcategory, now)
    destination = output / "inventory.json"
    report = {
        "format": INVENTORY_FORMAT,
        "schema_version": 1,
        "source_url": url,
        "category": category,
        "subcategory": subcategory,
        "checked_at": now.isoformat(),
        "max_pages": max_pages,
        "complete_listing": False,
        "programs": [],
        "unique_count": 0,
        "duplicate_items_count": 0,
        "pages_read": 0,
    }

    def checkpoint(progress: dict[str, Any]) -> None:
        report.update(progress)
        write_bundle(destination, report)
        if on_progress:
            on_progress(report)

    write_bundle(destination, report)
    try:
        listing = discover_programs(
            url, limit=None, start_rank=1, max_pages=max_pages, on_progress=checkpoint
        )
        report.update(listing)
    except (TvingError, ValueError, KeyError, TypeError) as exc:
        report.update(complete_listing=False, error=str(exc))
    report["checked_at"] = datetime.now(KST).isoformat()
    write_bundle(destination, report)
    return report, destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--category", choices=list(CATEGORIES), default="drama")
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--output-dir", type=Path, default=Path("data/tving-inventories"))
    args = parser.parse_args()

    def progress(value: dict) -> None:
        print(
            json.dumps({"pages": value["pages_read"], "unique_count": value["unique_count"]}),
            flush=True,
        )

    report, path = scan_inventory(
        args.output_dir,
        url=args.url or f"https://www.tving.com/more/genre/{CATEGORIES[args.category]['code']}",
        category=args.category,
        max_pages=args.max_pages,
        on_progress=progress,
    )
    print(
        json.dumps(
            {
                "inventory_file": str(path.resolve()),
                "complete_listing": report["complete_listing"],
                "unique_count": report["unique_count"],
                "error": report.get("error"),
            },
            ensure_ascii=False,
        )
    )
    if not report["complete_listing"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
