"""Common content fields; site-specific acquisition stays in separate modules."""

from __future__ import annotations

from typing import Any


def program_metadata(**fields: Any) -> dict[str, Any]:
    result: dict[str, Any] = dict.fromkeys([
        "program_id", "title", "content_type", "genre", "production_year", "channel",
        "directors", "writers", "cast", "synopsis", "keywords", "age_rating",
        "broadcast_start_date", "broadcast_end_date", "broadcast_schedule",
    ])
    result["episodes"] = []
    result.update(fields)
    return result
