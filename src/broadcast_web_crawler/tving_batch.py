"""Collect a configurable range of TVING drama or TV-show category listings."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from broadcast_web_crawler.output_paths import KST, create_run_folder, safe_folder_name
from broadcast_web_crawler.tving import (
    TvingError,
    _get_text,
    collect_program_with_report,
)

from .tving_storage import INDEX_FORMAT, index_entry

LISTING_URL = "https://www.tving.com/more/genre/PCA"
CATEGORIES = {
    "drama": {"name": "드라마", "home": "drama", "code": "PCA"},
    "entertainment": {"name": "예능", "home": "entertainment", "code": "PCD"},
}


def _category_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if (parts.scheme != "https" or parts.netloc.lower() != "www.tving.com"
            or not re.fullmatch(r"/more/genre/[A-Za-z0-9]+/?", parts.path)):
        raise ValueError("Expected https://www.tving.com/more/genre/<category-code>")
    return "https://www.tving.com" + parts.path.rstrip("/")


def category_name(category: str, url: str) -> str:
    """Resolve subcategory names from the live site's category navigation."""
    config = CATEGORIES[category]
    if url == f"https://www.tving.com/more/genre/{config['code']}":
        return "전체"
    html = _get_text(f"https://www.tving.com/{config['home']}")
    tag = BeautifulSoup(html, "html.parser").find("script", id="__NEXT_DATA__")
    if tag is None:
        raise TvingError("Missing category navigation")

    def search(node: Any) -> str | None:
        if isinstance(node, dict):
            if node.get("bandType") == "VOD_CATEGORY":
                for item in node.get("items", []):
                    if item.get("linkUrl") == url:
                        return str(item["title"])
            for value in node.values():
                found = search(value)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = search(item)
                if found:
                    return found
        return None

    label = search(json.loads(tag.get_text()))
    if not label:
        raise ValueError(f"URL is not in the selected {config['name']} category navigation")
    return label


def _listing_page(html: str, url: str) -> dict[str, Any]:
    tag = BeautifulSoup(html, "html.parser").find("script", id="__NEXT_DATA__")
    if tag is None:
        raise TvingError("Missing listing page data")
    props = json.loads(tag.get_text())["props"]["pageProps"]
    key = "/bff/web/v3/more/genre/" + url.rsplit("/", 1)[1]
    query = next((q for q in props["dehydratedState"]["queries"]
                  if q["queryKey"] == [key]), None)
    if query is None:
        raise TvingError("Missing category listing query")
    return query["state"]["data"]["pages"][0]["data"]


def discover_programs(
    url: str, *, limit: int | None, start_rank: int, max_pages: int,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Follow the listing's supplied nextApiUrl, preserving unique program order."""
    page = _listing_page(_get_text(url), url)
    order = page["order"]
    band = page["band"]
    programs: list[dict[str, Any]] = []
    seen: set[str] = set()
    visited: set[str] = set()
    target = None if limit is None else start_rank + limit - 1
    pages = 1
    duplicates = 0
    stagnant_pages = 0
    while True:
        previous_count = len(programs)
        for item in band["items"]:
            code = item["code"]
            if code in seen:
                duplicates += 1
                continue
            if not re.fullmatch(r"P[0-9]+", code):
                raise TvingError("Listing returned a non-program content ID")
            seen.add(code)
            programs.append({
                "rank": len(programs) + 1, "title": item["title"],
                "url": f"https://www.tving.com/contents/{code}",
            })
        stagnant_pages = stagnant_pages + 1 if len(programs) == previous_count else 0
        next_path = band.get("nextApiUrl")
        if on_progress:
            on_progress({"source_url": url, "order": order, "pages_read": pages,
                         "programs": programs, "unique_count": len(programs),
                         "duplicate_items_count": duplicates, "complete_listing": not next_path})
        if target is not None and len(programs) >= target:
            break
        if not next_path:
            if target is not None:
                raise TvingError(
                    f"Category has only {len(programs)} programs; requested rank {target}"
                )
            break
        if stagnant_pages >= 3:
            raise TvingError("Listing pagination made no progress for three pages")
        if pages >= max_pages:
            raise TvingError("Listing page limit reached; increase --max-pages or narrow the range")
        next_url = urljoin("https://gw.tving.com", next_path)
        parts = urlsplit(next_url)
        if (parts.scheme != "https" or parts.netloc != "gw.tving.com"
                or not parts.path.startswith("/bff/web/v3/content/vod") or next_url in visited):
            raise TvingError("Unexpected or repeated listing pagination URL")
        visited.add(next_url)
        time.sleep(1)
        payload = json.loads(_get_text(next_url))
        if payload.get("code") != "0000" or not isinstance(payload.get("data"), dict):
            raise TvingError("Listing pagination API failed")
        data = payload["data"]
        band = data.get("band", data)
        if (not isinstance(band.get("items"), list)
                or (not band["items"] and band.get("nextApiUrl"))):
            raise TvingError("Pagination returned no items while advertising more results")
        pages += 1
    selected = programs[start_rank - 1:target]
    if not selected:
        raise TvingError("Requested starting rank is beyond the category listing")
    return {
        "source_url": url, "order": order, "pages_read": pages,
        "unique_count": len(programs), "duplicate_items_count": duplicates,
        "complete_listing": not band.get("nextApiUrl"),
        "programs": selected,
    }


def save_batch(result: dict[str, Any], destination: Path) -> None:
    """Store references to source bundles rather than another metadata copy."""
    programs = [index_entry(row["data"]["bundle"],
                            f"{row['folder']}/{row['data']['metadata_file']}")
                for row in result["programs"]
                if row["status"] == "success"]
    destination.write_text(json.dumps({"format": INDEX_FORMAT, "schema_version": 1,
                                      "programs": programs}, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    report = {key: value for key, value in result.items() if key != "programs"}
    report["programs"] = [{
        **{key: value for key, value in row.items() if key != "data"},
        **({"complete_episode_list": row["data"]["episode_list"][
            "complete_for_current_api_listing"],
            "metadata_file": f"{row['folder']}/{row['data']['metadata_file']}"}
           if row["status"] == "success" else {}),
    } for row in result["programs"]]
    destination.with_name("collection-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def parse_listing(html: str, limit: int = 20) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be positive")
    page = _listing_page(html, LISTING_URL)
    items = page["band"]["items"]
    programs = []
    seen = set()
    for item in items:
        if item["code"] in seen:
            continue
        seen.add(item["code"])
        programs.append({
            "rank": len(programs) + 1,
            "title": item["title"],
            "url": f"https://www.tving.com/contents/{item['code']}",
        })
        if len(programs) >= limit:
            break
    if len(programs) < limit:
        raise TvingError(f"Listing has only {len(programs)} programs; expected {limit}")
    return {"source_url": LISTING_URL, "order": page["order"], "programs": programs}


def collect_top_programs(
    output_dir: Path, limit: int | None = 20, *, start_rank: int = 1,
    category: str = "drama", url: str | None = None, max_pages: int = 500,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    if start_rank < 1 or max_pages < 1:
        raise ValueError("start_rank and max_pages must be positive")
    if category not in CATEGORIES:
        raise ValueError("category must be drama or entertainment")
    config = CATEGORIES[category]
    url = _category_url(url or f"https://www.tving.com/more/genre/{config['code']}")
    if inventory is not None:
        from .tving_inventory import validate_inventory

        validate_inventory(inventory, url=url, category=category)
        subcategory = inventory["subcategory"]
    else:
        subcategory = category_name(category, url)
    started = datetime.now(KST)
    if inventory is not None:
        target = None if limit is None else start_rank + limit - 1
        entries = inventory["programs"][start_rank - 1:target]
        if not entries or (limit is not None and len(entries) != limit):
            raise ValueError("Requested range is outside the saved inventory")
        listing = {"source_url": url, "order": inventory["order"],
                   "pages_read": inventory["pages_read"], "programs": entries,
                   "inventory_checked_at": inventory["checked_at"],
                   "complete_listing": True}
    else:
        listing = discover_programs(url, limit=limit, start_rank=start_rank, max_pages=max_pages)
    output_dir = create_run_folder(output_dir, config["name"], subcategory, started)
    result: dict[str, Any] = {
        "started_at": started.isoformat(),
        "output_dir": str(output_dir.resolve()),
        "scope": {"category": config["name"], "subcategory": subcategory,
                  "limit": limit, "start_rank": start_rank, "max_pages": max_pages},
        "listing": listing,
        "programs": [],
        "summary": {},
    }
    destination = output_dir / "contents.json"
    date = started.strftime("%Y%m%d")
    for entry in listing["programs"]:
        folder_name = f"{safe_folder_name(entry['title'])}_{date}"
        program_dir = output_dir / folder_name
        suffix = 2
        while program_dir.exists():
            program_dir = output_dir / f"{folder_name}_{suffix}"
            suffix += 1
        entry = {**entry, "folder": program_dir.name}
        try:
            program = collect_program_with_report(entry["url"], program_dir)
            episodes = program["episode_list"]
            synopsis_count = sum(bool((row.get("synopsis") or "").strip())
                                 for row in episodes["episodes"])
            record = {
                **entry, "status": "success", "data": program,
                "synopsis_count": synopsis_count,
                "missing_synopsis_episode_codes": [
                    row["episode_code"] for row in episodes["episodes"]
                    if not (row.get("synopsis") or "").strip()
                ],
            }
            print(json.dumps({
                "rank": entry["rank"], "title": entry["title"],
                "episodes": episodes["collected_count"],
                "synopses": synopsis_count,
                "complete": episodes["complete_for_current_api_listing"],
            }, ensure_ascii=False), flush=True)
        except (TvingError, ValueError, KeyError, TypeError) as exc:
            record = {**entry, "status": "error", "error": str(exc)}
            print(json.dumps(record, ensure_ascii=False), flush=True)
        result["programs"].append(record)
        successes = [row for row in result["programs"] if row["status"] == "success"]
        result["summary"] = {
            "requested_programs": len(listing["programs"]) if limit is None else limit,
            "processed_programs": len(result["programs"]),
            "successful_programs": len(successes),
            "failed_programs": len(result["programs"]) - len(successes),
            "complete_episode_lists": sum(
                row["data"]["episode_list"]["complete_for_current_api_listing"]
                for row in successes
            ),
            "collected_episodes": sum(
                row["data"]["episode_list"]["collected_count"] for row in successes
            ),
            "episodes_with_synopsis": sum(row["synopsis_count"] for row in successes),
        }
        save_batch(result, destination)
        if on_progress:
            on_progress({"processed": len(result["programs"]),
                         "total": len(listing["programs"]), "title": entry["title"],
                         "content_file": str(destination.resolve()),
                         "summary": result["summary"]})
        time.sleep(1)
    result["finished_at"] = datetime.now(KST).isoformat()
    save_batch(result, destination)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/tving"),
                        help="Parent folder; each run creates a new timestamped child")
    parser.add_argument("--category", choices=list(CATEGORIES), default="drama")
    parser.add_argument(
        "--url", help="TVING genre URL; defaults to the selected category's all tab"
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--limit", type=int, default=20, help="Number of programs (default: 20)")
    scope.add_argument("--all", action="store_true", help="Collect until the category listing ends")
    parser.add_argument("--start-rank", type=int, default=1, help="First rank, starting at 1")
    parser.add_argument("--max-pages", type=int, default=500, help="Listing pagination bound")
    parser.add_argument("--inventory-file", type=Path,
                        help="Use a completed saved category inventory")
    args = parser.parse_args()
    inventory = (json.loads(args.inventory_file.read_text(encoding="utf-8"))
                 if args.inventory_file else None)
    result = collect_top_programs(
        args.output_dir, None if args.all else args.limit, start_rank=args.start_rank,
        category=args.category, url=args.url or (inventory["source_url"] if inventory else None),
        max_pages=args.max_pages, inventory=inventory,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"Saved JSON: {Path(result['output_dir']) / 'contents.json'}")


if __name__ == "__main__":
    main()
