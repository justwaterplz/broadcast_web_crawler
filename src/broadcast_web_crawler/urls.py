"""Pure URL normalization, origin checks, and link scoring."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

_TRACKING_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "referrer",
    }
)
_PROGRAM_TERMS = (
    "program",
    "programme",
    "show",
    "series",
    "content",
    "vod",
    "detail",
    "episode",
    "프로그램",
    "방송",
)
_LIST_TERMS = ("category", "programs", "shows", "schedule", "list", "편성", "목록")


def _is_tracking_key(key: str) -> bool:
    lowered = key.casefold()
    return lowered.startswith("utm_") or lowered in _TRACKING_KEYS


def canonicalize_url(url: str, *, base_url: str | None = None) -> str | None:
    """Return a stable HTTP(S) URL, or ``None`` for unsupported/invalid URLs."""
    absolute = urljoin(base_url, url) if base_url else url
    try:
        parts = urlsplit(absolute.strip())
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.casefold()
    if scheme not in {"http", "https"} or not hostname or parts.username or parts.password:
        return None

    host = hostname.casefold().rstrip(".")
    if ":" in host:
        host = f"[{host}]"
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default_port else f"{host}:{port}"

    path = re.sub(r"/{2,}", "/", parts.path or "/")
    path = quote(path, safe="/%:@!$&'()*+,;=-._~")
    path = re.sub(r"%[0-9a-fA-F]{2}", lambda match: match.group().upper(), path)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_key(key)
    ]
    query = urlencode(sorted(query_items), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def same_origin(left: str, right: str) -> bool:
    def origin(url: str) -> tuple[str, str, int | None] | None:
        canonical = canonicalize_url(url)
        if canonical is None:
            return None
        parts = urlsplit(canonical)
        default = 80 if parts.scheme == "http" else 443
        return parts.scheme, parts.hostname or "", parts.port or default

    return origin(left) == origin(right) and origin(left) is not None


def score_program_url(url: str, *, anchor_text: str = "") -> float:
    """Score a link as a likely program/detail page using explainable signals."""
    parts = urlsplit(url)
    haystack = f"{parts.path} {anchor_text}".casefold()
    score = 0.0
    score += min(sum(term in haystack for term in _PROGRAM_TERMS) * 1.5, 4.5)
    score -= min(sum(term in haystack for term in _LIST_TERMS) * 1.0, 2.0)
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) >= 2:
        score += 0.5
    if re.search(r"(?:^|[-_/])\d{2,}(?:$|[-_/])", parts.path):
        score += 1.0
    if any(
        key.casefold() in {"id", "programid", "contentid", "seq"}
        for key, _ in parse_qsl(parts.query)
    ):
        score += 1.5
    return max(score, 0.0)
