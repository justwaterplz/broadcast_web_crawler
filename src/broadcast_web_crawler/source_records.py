"""Source snapshots and review state, kept separate from content-only JSON."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(present(v) for v in value.values())
    if isinstance(value, list):
        return any(present(v) for v in value)
    return True


def source_record(
    content: dict[str, Any], *, source: str, url: str, collected_at: str,
    method: str, field_origins: dict[str, str] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record source claims without promoting them to validated facts."""
    hosts = {
        "tving": {"www.tving.com", "tving.com"},
        "namuwiki": {"namu.wiki"},
        "cjenm": {"www.cjenm.com", "cjenm.com", "web2-cf-api.cjenm.com"},
    }
    parts = urlsplit(url)
    if (source not in hosts or parts.scheme != "https" or parts.netloc not in hosts[source]
            or parts.username or parts.password):
        raise ValueError("Source URL does not match the declared source")
    if not collected_at or not method or not present(content.get("title")):
        raise ValueError("Title, source time and acquisition method are required")
    if datetime.fromisoformat(collected_at).tzinfo is None:
        raise ValueError("Source time must include its timezone")
    claims = deepcopy(content)
    digest = hashlib.sha256(json.dumps(
        claims, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    identity = hashlib.sha256(f"{source}\n{url}\n{collected_at}\n{digest}".encode()).hexdigest()
    flags = []
    if source == "namuwiki":
        flags.append({"code": "community_edited", "field": "*",
                      "reason": "공동 편집 문서: 공식 출처 대조와 사실·평가 구분이 필요합니다."})
    origins = field_origins or {}
    return {
        "schema_version": 1, "record_id": f"{source}:{identity[:24]}",
        "source": source, "source_url": url, "collected_at": collected_at,
        "acquisition_method": method, "content_sha256": digest, "content": claims,
        "field_provenance": {
            k: {"source_url": url, "collected_at": collected_at,
                "extraction_path": origins.get(k), "review_status": "unreviewed"}
            for k, v in claims.items() if present(v)
        },
        "evidence": deepcopy(evidence or {}),
        "review": {"status": "pending" if flags else "unreviewed", "flags": flags},
    }


def save_source_record(path: Path, record: dict[str, Any]) -> None:
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_source_record(record: dict[str, Any]) -> None:
    if record.get("schema_version") != 1 or not isinstance(record.get("content"), dict):
        raise ValueError("Unsupported source record")
    expected = source_record(record["content"], source=record["source"],
                             url=record["source_url"], collected_at=record["collected_at"],
                             method=record["acquisition_method"])
    if (expected["content_sha256"] != record.get("content_sha256")
            or expected["record_id"] != record.get("record_id")):
        raise ValueError("Source content or identity changed; create a new source record")


def tving_source_record(captured: dict[str, Any], content: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "program_id": "program_code", "title": "title", "content_type": "category_name",
        "genre": "genre_name", "production_year": "product_year", "channel": "channel",
        "directors": "director", "writers": "script", "cast": "actor",
        "synopsis": "synopsis", "keywords": "keywords",
        "broadcast_start_date": "broad_dt", "broadcast_end_date": "broad_end_dt",
        "broadcast_schedule": "broad_week/broad_hour/broad_minu",
    }
    origins = {k: "__NEXT_DATA__.props.pageProps.contentInfo." + v for k, v in fields.items()}
    origins.update(age_rating='JSON-LD.TVSeries.contentRating', episodes='body.result[].episode')
    return source_record(
        content, source="tving", url=captured["source_url"],
        collected_at=captured["collected_at"], method="embedded_page_data_and_episode_api",
        field_origins=origins,
        evidence={"episode_endpoint": captured["source_endpoint"],
                  "episode_scope": {k: v for k, v in captured["episode_list"].items()
                                    if k != "episodes"}},
    )


def wiki_source_record(
    content: dict[str, Any], report: dict[str, Any],
) -> dict[str, Any]:
    labels = {
        "genre": "장르", "channel": "채널", "production_company": "제작사/제작",
        "directors": "연출", "writers": "극본/작가", "cast": "출연", "hosts": "진행",
        "age_rating": "시청 등급", "broadcast_start_date": "방송 기간/공개 기간/공개일",
        "broadcast_end_date": "방송 기간/공개 기간/공개일", "broadcast_schedule": "방송 시간",
        "episode_count": "방송 횟수/공개 회차",
    }
    return source_record(
        content, source="namuwiki",
        url=report.get("metadata_source_url") or report["final_url"],
        collected_at=report["checked_at"], method="wiki_infobox_and_selected_sections",
        field_origins={k: "infobox." + v for k, v in labels.items()},
        evidence={"infobox_fields": report.get("infobox_fields", {}),
                  "content_sections": content.get("content_sections", {}),
                  "related_documents_checked": report.get("related_documents_checked", False)},
    )
