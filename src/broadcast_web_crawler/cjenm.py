"""Parse saved CJ ENM JSON responses. This module makes no network requests."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .metadata import program_metadata
from .output_paths import KST, create_run_folder, safe_folder_name
from .tving_storage import write_bundle

BUNDLE_FORMAT = "cjenm-source-bundle"
INDEX_FORMAT = "cjenm-source-index"


def normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if (parts.scheme != "https" or parts.netloc.lower() not in {"www.cjenm.com", "cjenm.com"}
            or not re.fullmatch(r"/(?:ko|en)/featured-contents/[^/]+/?", parts.path)):
        raise ValueError("CJ ENM 공식 작품 상세 URL을 입력해 주세요.")
    return urlunsplit(("https", "www.cjenm.com", parts.path.rstrip("/") + "/", "", ""))


def inspect_saved_responses(url: str, program: dict, characters: dict | None = None) -> dict:
    url = normalize_url(url)
    info = _data(program)
    if (not isinstance(info.get("pgmNm"), str) or not info["pgmNm"].strip()
            or not str(info.get("pgmSeq", "")).isdigit()):
        raise ValueError("작품명과 작품 ID가 있는 CJ ENM 응답을 선택해 주세요.")
    if characters is not None:
        people = _data(characters)
        if people.get("pgmSeq") and str(people["pgmSeq"]) != str(info["pgmSeq"]):
            raise ValueError("등장인물 응답과 작품 응답의 ID가 다릅니다.")
    return {"url": url, "kind": "cjenm_detail", "site": "CJ ENM", "status": "ready",
            "title": info["pgmNm"], "program_id": str(info["pgmSeq"]),
            "scope": "사용자가 저장한 응답", "source_binding": "requires_user_confirmation",
            "checked_at": datetime.now(KST).isoformat()}


def import_saved_responses(
    url: str, program: dict, output_root: Path, *, characters: dict | None = None,
    confirmed_target: bool = False, review: dict | None = None,
) -> dict:
    if confirmed_target is not True:
        raise ValueError("공식 URL과 응답 파일이 같은 작품인지 확인해 주세요.")
    inspected = inspect_saved_responses(url, program, characters)
    now = datetime.now(KST)
    run = create_run_folder(output_root, "CJ_ENM", "응답가져오기", now)
    show = run / f"{safe_folder_name(inspected['title'])}_{now:%Y%m%d}"
    bundle = {"format": BUNDLE_FORMAT, "schema_version": 1, "programResponse": program,
              "collection": {"source_url": inspected["url"], "collected_at": now.isoformat(),
                  "acquisition_method": "user_saved_responses", "status": "imported",
                  "network_requests": 0, "target_review": review or inspected,
                  "imported_at": now.isoformat(), "source_capture_time": None,
                  "source_binding": "user_confirmed", "confirmed_target": True}}
    if characters is not None:
        bundle["charactersResponse"] = characters
    destination = show / "metadata.json"
    write_bundle(destination, bundle)
    relative = destination.relative_to(run).as_posix()
    write_bundle(run / "contents.json", {"format": INDEX_FORMAT, "schema_version": 1,
        "programs": [{"title": inspected["title"], "metadata_file": relative}]})
    report = {"source_url": inspected["url"], "output_dir": str(run.resolve()),
              "metadata_file": relative, "acquisition_method": "user_saved_responses",
              "summary": {"successful_programs": 1}, "target_review": review or inspected}
    write_bundle(run / "collection-report.json", report)
    return report


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("resultCd") != "0000":
        raise ValueError("CJ ENM response is not successful")
    data = (payload.get("result") or {}).get("data")
    if not isinstance(data, dict):
        raise ValueError("Missing CJ ENM response data")
    return data


def parse_saved_responses(
    program: dict[str, Any], characters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    info = _data(program)
    if not info.get("pgmNm") or not info.get("pgmSeq"):
        raise ValueError("Missing CJ ENM program identity")

    def names(value: Any) -> list[str] | None:
        return [v.strip() for v in re.split(r"[,·]", str(value)) if v.strip()] if value else None

    def date(value: Any) -> str | None:
        return datetime.fromtimestamp(value / 1000, KST).date().isoformat() if value else None

    people = []
    if characters is not None:
        for group in _data(characters).get("detailPrsnInfoList") or []:
            for person in group.get("pgmPrsnIntrcnInfoList") or []:
                people.append({"source_person_id": person.get("pgmPrsnSeq"),
                               "name": person.get("prsnNm"),
                               "description": person.get("dtlDescpCnts")})
    count = str(info.get("allEpino") or "")
    return program_metadata(
        program_id=str(info["pgmSeq"]), title=info["pgmNm"],
        content_type=info.get("repGenreNm"), genre=info.get("ptclrGenreInfo"),
        synopsis=info.get("pgmDescp"), directors=names(info.get("pdNm")),
        writers=names(info.get("writrNm")), cast=names(info.get("playrsNm")),
        channel=", ".join(c["chnNm"] for c in info.get("chnInfoList") or []) or None,
        age_rating=info.get("dlbrtGrd"), production_company=info.get("mkComNm") or None,
        broadcast_start_date=date(info.get("bdStrDt")),
        broadcast_end_date=date(info.get("bdEndDt")),
        episode_count=int(count) if count.isdigit() else None,
        tving_url=info.get("pgmReplayUrlAddr"), characters=people,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="CJ ENM 공식 URL과 저장한 원본 응답 가져오기")
    parser.add_argument("url")
    parser.add_argument("--program-response", type=Path, required=True)
    parser.add_argument("--characters-response", type=Path)
    parser.add_argument("--confirmed-target", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("data/cjenm"))
    args = parser.parse_args()
    program = json.loads(args.program_response.read_text(encoding="utf-8-sig"))
    people = (json.loads(args.characters_response.read_text(encoding="utf-8-sig"))
              if args.characters_response else None)
    report = import_saved_responses(args.url, program, args.output_dir, characters=people,
                                    confirmed_target=args.confirmed_target)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
