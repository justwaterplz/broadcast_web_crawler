"""Compare explicitly matched source snapshots without overwriting source claims."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .cjenm import parse_saved_responses
from .output_paths import KST, create_run_folder
from .source_records import present, source_record, validate_source_record


def compare_sources(
    records: list[dict[str, Any]], *, title: str, confirmed_same_program: bool,
) -> dict[str, Any]:
    if confirmed_same_program is not True:
        raise ValueError("Confirm that the supplied URLs identify the same program first")
    if len(records) < 2 or not title.strip():
        raise ValueError("A title and at least two source records are required")
    for record in records:
        validate_source_record(record)
    identities = [(r["source"], r["source_url"]) for r in records]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate source documents must not count as corroboration")
    fields = sorted({k for r in records for k in r["content"]} - {"program_id", "episodes"})
    comparison = {}
    for field in fields:
        claims = [{"record_id": r["record_id"], "source": r["source"],
                   "source_url": r["source_url"], "collected_at": r["collected_at"],
                   "value": deepcopy(r["content"][field]),
                   "review_status": r["field_provenance"].get(field, {}).get(
                       "review_status", "unreviewed")}
                  for r in records if present(r["content"].get(field))]
        values = {json.dumps(c["value"], ensure_ascii=False, sort_keys=True) for c in claims}
        state = ("missing" if not claims else "single_source" if len(claims) == 1
                 else "same_value" if len(values) == 1 else "different_values")
        comparison[field] = {"status": state, "claims": claims,
                             "missing_sources": [r["record_id"] for r in records
                                                 if not present(r["content"].get(field))]}
    return {
        "schema_version": 1, "title": title, "identity_confirmed_by_user": True,
        "created_at": datetime.now(KST).isoformat(),
        "sources": deepcopy(records), "fields": comparison,
        "episode_coverage": [{"record_id": r["record_id"], "source": r["source"],
                              "collected_episodes": len(r["content"].get("episodes") or []),
                              "synopsis_count": sum(present(e.get("synopsis"))
                                                    for e in r["content"].get("episodes") or [])}
                             for r in records],
        "review": {"status": "pending", "notes": [
            "같은 값이어도 사실 검증이 완료된 것은 아닙니다.",
            "서로 다른 값은 오류·모순으로 단정하지 않고 범위·표현·수집 시점을 검토합니다.",
            "위키 서술은 검토 전 확정 정보로 채택하지 않습니다.",
        ]},
    }


def load_manifest(path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Read only local, explicitly selected documents. Never route by guessed titles."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("confirmed_same_program") is not True:
        raise ValueError("Manifest needs confirmed_same_program=true after URL review")

    def load(filename: str) -> Any:
        return json.loads((path.parent / filename).read_text(encoding="utf-8"))

    records = []
    for item in manifest["sources"]:
        if "record_file" in item:
            records.append(load(item["record_file"]))
            continue
        if "program_response_file" in item:
            if item["source"] != "cjenm":
                raise ValueError("Saved response import currently supports CJ ENM")
            content = parse_saved_responses(
                load(item["program_response_file"]),
                load(item["characters_response_file"]) if item.get("characters_response_file")
                else None,
            )
        else:
            data = load(item["content_file"])
            if "programs" in data:
                matches = [p for p in data["programs"]
                           if p.get("program_id") == item.get("program_id")]
                if len(matches) != 1:
                    raise ValueError("Select exactly one program_id from the collection")
                content = matches[0]
            else:
                content = data
        original = deepcopy(content)
        records.append(source_record(
            content, source=item["source"], url=item["source_url"],
            collected_at=item["collected_at"], method=item["acquisition_method"],
            evidence={"saved_content": original,
                      "source_time_basis": item.get("source_time_basis", "source_capture_time"),
                      "input_files": {
                k: str((path.parent / item[k]).resolve()) for k in (
                    "content_file", "program_response_file", "characters_response_file",
                ) if k in item}},
        ))
    return manifest["title"], records


def save_comparison(result: dict[str, Any], root: Path) -> Path:
    output = create_run_folder(root, "출처비교", result["title"], datetime.now(KST))
    destination = output / "comparison.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/comparisons"))
    args = parser.parse_args()
    title, records = load_manifest(args.manifest)
    result = compare_sources(records, title=title, confirmed_same_program=True)
    print(f"Saved comparison: {save_comparison(result, args.output_dir)}")


if __name__ == "__main__":
    main()
