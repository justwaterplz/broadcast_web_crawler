"""One source-preserving TVING JSON per program, with reference-only run indexes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .output_paths import KST, create_run_folder

BUNDLE_FORMAT = "tving-source-bundle"
INDEX_FORMAT = "tving-source-index"
BUNDLE_FILENAME = "metadata.json"


def make_bundle(info: dict, json_ld: list, collection: dict) -> dict[str, Any]:
    """Wrap source objects; do not flatten, rename or deduplicate source fields."""
    return {"format": BUNDLE_FORMAT, "schema_version": 1, "collection": collection,
            "contentInfo": info, "jsonLd": json_ld}


def write_bundle(destination: Path, bundle: dict) -> None:
    """Checkpoint one JSON without leaving a partially written destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)


def display_content(bundle: dict) -> dict[str, Any]:
    """Build an in-memory UI view, never save a second copy of source metadata."""
    from .tving import _without_images, content_metadata, parse_episodes

    info = bundle["contentInfo"]
    return content_metadata({
        "detail": _without_images({"content_info": info, "json_ld": bundle["jsonLd"]}),
        "episode_list": parse_episodes(bundle["episodeApi"], info["program_code"]),
    })


def index_entry(bundle: dict, relative_file: str) -> dict[str, Any]:
    """Keep just a navigation title and file reference, without copying metadata."""
    return {"title": bundle["contentInfo"].get("title"), "metadata_file": relative_file}


def consolidate_run(source: Path, output_root: Path) -> Path:
    """Copy a legacy raw-enabled run into new bundles; leave source files untouched."""
    source = source.resolve()
    folders = sorted({p.parent for p in source.glob("*/content-info.raw.json")})
    if not folders:
        raise ValueError("No source content-info.raw.json files found in this run")
    previous_report_file = source / "collection-report.json"
    previous_report = (json.loads(previous_report_file.read_text(encoding="utf-8"))
                       if previous_report_file.exists() else {})
    order = {row["folder"]: i for i, row in enumerate(previous_report.get("programs", []))
             if "folder" in row}
    folders.sort(key=lambda folder: (order.get(folder.name, len(order)), folder.name))
    # Read and validate every input before creating an output run.
    bundles = []
    for folder in folders:
        def load(filename: str, directory: Path = folder) -> Any:
            return json.loads((directory / filename).read_text(encoding="utf-8"))

        report = load("collection-report.json")
        record_file = folder / "source-record.json"
        record = load("source-record.json") if record_file.exists() else {}
        collection = {key: report[key] for key in (
            "source_url", "collected_at", "acquisition_method", "complete_for_current_api_listing",
        ) if key in report}
        collection["status"] = "collected"
        endpoint = record.get("evidence", {}).get("episode_endpoint")
        if endpoint:
            collection["episode_endpoint"] = endpoint
        bundle = make_bundle(load("content-info.raw.json"), load("json-ld.raw.json"), collection)
        bundle["episodeApi"] = load("episodes-api.raw.json")
        # No source-record content or display projection is imported.
        bundles.append((folder.name, bundle))
    scope = previous_report.get("scope", {})
    run = create_run_folder(output_root, scope.get("category", "TVING"),
                            scope.get("subcategory", "작품") + "_통합", datetime.now(KST))
    entries = []
    for folder_name, bundle in bundles:
        relative = f"{folder_name}/{BUNDLE_FILENAME}"
        write_bundle(run / relative, bundle)
        entries.append(index_entry(bundle, relative))
    index = {"format": INDEX_FORMAT, "schema_version": 1, "programs": entries}
    (run / "contents.json").write_text(json.dumps(index, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    report = {"operation": "consolidate_saved_sources", "input_run": str(source),
              "created_at": datetime.now(KST).isoformat(), "scope": scope,
              "program_count": len(entries), "source_files_preserved": True,
              "source_payloads_modified": False}
    (run / "collection-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-run", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/tving"))
    args = parser.parse_args()
    print(consolidate_run(args.input_run, args.output_dir))


if __name__ == "__main__":
    main()
