"""Deterministic HTML Bronze-to-Silver extraction."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from typing import Any, cast

from bs4 import BeautifulSoup, Tag
from pydantic import JsonValue

from .contracts import SilverDocument, SilverTable
from .urls import canonicalize_url

_SPACE = re.compile(r"\s+")


def _clean(value: str) -> str:
    return _SPACE.sub(" ", value).strip()


def _normalized_json(value: Any) -> JsonValue:
    if isinstance(value, Mapping):
        return {
            str(key): _normalized_json(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        return [_normalized_json(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return cast(JsonValue, value)
    return str(value)


def _metadata(soup: BeautifulSoup) -> tuple[tuple[str, tuple[str, ...]], ...]:
    found: defaultdict[str, list[str]] = defaultdict(list)
    for element in soup.find_all("meta"):
        key = next(
            (
                str(element.get(attribute))
                for attribute in ("name", "property", "itemprop", "http-equiv")
                if element.get(attribute)
            ),
            "",
        )
        content = element.get("content")
        if key and content:
            cleaned = _clean(str(content))
            if cleaned and cleaned not in found[key.casefold()]:
                found[key.casefold()].append(cleaned)
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    if isinstance(canonical, Tag) and canonical.get("href"):
        found["canonical"].append(str(canonical["href"]))
    return tuple((key, tuple(found[key])) for key in sorted(found))


def _json_ld(soup: BeautifulSoup) -> tuple[JsonValue, ...]:
    values: list[JsonValue] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        values.append(_normalized_json(parsed))
    return tuple(values)


def _unique_columns(values: list[str], width: int) -> tuple[str, ...]:
    seen: defaultdict[str, int] = defaultdict(int)
    columns: list[str] = []
    for index in range(width):
        base = values[index] if index < len(values) and values[index] else f"column_{index + 1}"
        seen[base] += 1
        columns.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return tuple(columns)


def _tables(soup: BeautifulSoup) -> tuple[SilverTable, ...]:
    tables: list[SilverTable] = []
    for table in soup.find_all("table"):
        rows: list[list[str]] = []
        header_index: int | None = None
        for row in table.find_all("tr"):
            cells = [_clean(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
                if header_index is None and row.find("th") is not None:
                    header_index = len(rows) - 1
        if not rows:
            continue
        width = max(len(row) for row in rows)
        headers = rows[header_index] if header_index is not None else []
        data_rows = [row for index, row in enumerate(rows) if index != header_index]
        normalized_rows = tuple(tuple((*row, *([""] * (width - len(row))))) for row in data_rows)
        caption_tag = table.find("caption")
        caption = _clean(caption_tag.get_text(" ", strip=True)) if caption_tag else None
        tables.append(
            SilverTable(
                caption=caption or None,
                columns=_unique_columns(headers, width),
                rows=normalized_rows,
            )
        )
    return tuple(tables)


def _lists(soup: BeautifulSoup) -> tuple[tuple[str, ...], ...]:
    values: list[tuple[str, ...]] = []
    for element in soup.find_all(["ul", "ol"]):
        if element.find_parent(["ul", "ol"]) is not None:
            continue
        items = tuple(
            text
            for item in element.find_all("li", recursive=False)
            if (text := _clean(item.get_text(" ", strip=True)))
        )
        if items:
            values.append(items)
    return tuple(values)


def parse_html(
    content: bytes | str,
    *,
    source_url: str,
    content_sha256: str | None = None,
) -> SilverDocument:
    """Parse one HTML object into a stable, serializable Silver document."""
    raw = content.encode("utf-8") if isinstance(content, str) else content
    digest = content_sha256 or hashlib.sha256(raw).hexdigest()
    html = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    title = _clean(soup.title.get_text(" ", strip=True)) if soup.title else None
    metadata = _metadata(soup)
    json_ld = _json_ld(soup)
    tables = _tables(soup)
    lists = _lists(soup)

    for unwanted in soup.find_all(["script", "style", "noscript", "template"]):
        unwanted.decompose()
    text_root = soup.find("main") or soup.find("article") or soup.body or soup
    text = _clean(text_root.get_text(" ", strip=True))

    stable_url = canonicalize_url(source_url) or source_url.strip()
    document_id = hashlib.sha256(f"{stable_url}\0{digest}".encode()).hexdigest()
    return SilverDocument(
        document_id=document_id,
        source_url=stable_url,
        content_sha256=digest,
        title=title or None,
        metadata=metadata,
        json_ld=json_ld,
        tables=tables,
        lists=lists,
        text=text,
    )
