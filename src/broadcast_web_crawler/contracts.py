"""Pydantic contracts shared by capture, storage, and parsing layers."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CrawlPhase(StrEnum):
    QUEUED = "queued"
    DISCOVERING = "discovering"
    CAPTURING = "capturing"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    LOADING = "loading"
    COMPLETED = "completed"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[CrawlPhase, frozenset[CrawlPhase]] = {
    CrawlPhase.QUEUED: frozenset({CrawlPhase.DISCOVERING, CrawlPhase.FAILED}),
    CrawlPhase.DISCOVERING: frozenset({CrawlPhase.CAPTURING, CrawlPhase.FAILED}),
    CrawlPhase.CAPTURING: frozenset({CrawlPhase.PARSING, CrawlPhase.FAILED}),
    CrawlPhase.PARSING: frozenset({CrawlPhase.EXTRACTING, CrawlPhase.FAILED}),
    CrawlPhase.EXTRACTING: frozenset({CrawlPhase.VALIDATING, CrawlPhase.FAILED}),
    CrawlPhase.VALIDATING: frozenset({CrawlPhase.LOADING, CrawlPhase.FAILED}),
    CrawlPhase.LOADING: frozenset({CrawlPhase.COMPLETED, CrawlPhase.FAILED}),
    CrawlPhase.COMPLETED: frozenset(),
    CrawlPhase.FAILED: frozenset(),
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CrawlTransition(Contract):
    from_phase: CrawlPhase
    to_phase: CrawlPhase
    at: AwareDatetime = Field(default_factory=_utc_now)
    reason: str | None = None


class CrawlRun(Contract):
    run_id: UUID = Field(default_factory=uuid4)
    start_url: str
    phase: CrawlPhase = CrawlPhase.QUEUED
    created_at: AwareDatetime = Field(default_factory=_utc_now)
    updated_at: AwareDatetime = Field(default_factory=_utc_now)
    transitions: tuple[CrawlTransition, ...] = ()
    error: str | None = None

    def transition(
        self,
        to_phase: CrawlPhase,
        *,
        reason: str | None = None,
        at: datetime | None = None,
    ) -> CrawlRun:
        if to_phase not in _ALLOWED_TRANSITIONS[self.phase]:
            raise ValueError(f"invalid crawl transition: {self.phase} -> {to_phase}")
        if to_phase is CrawlPhase.FAILED and not reason:
            raise ValueError("failed transitions require a reason")
        timestamp = at or _utc_now()
        event = CrawlTransition(
            from_phase=self.phase,
            to_phase=to_phase,
            at=timestamp,
            reason=reason,
        )
        return self.model_copy(
            update={
                "phase": to_phase,
                "updated_at": timestamp,
                "transitions": (*self.transitions, event),
                "error": reason if to_phase is CrawlPhase.FAILED else None,
            }
        )


class ObjectRef(Contract):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)
    media_type: str = "application/octet-stream"


class CapturedResource(Contract):
    url: str
    status: int = Field(ge=100, le=599)
    object: ObjectRef
    headers: tuple[tuple[str, str], ...] = ()
    kind: str = "response"


class CapturedImage(Contract):
    url: str
    alt: str = ""
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    kind: str
    object: ObjectRef | None = None


class PageCapture(Contract):
    url: str
    depth: int = Field(ge=0)
    score: float = Field(ge=0)
    html: ObjectRef
    resources: tuple[CapturedResource, ...] = ()
    images: tuple[CapturedImage, ...] = ()
    links: tuple[str, ...] = ()


class CaptureManifest(Contract):
    format_version: int = 1
    run_id: UUID
    start_url: str
    captured_at: AwareDatetime
    pages: tuple[PageCapture, ...]
    total_bytes: int = Field(ge=0)


class BronzeDocument(Contract):
    source_url: str
    captured_at: AwareDatetime
    content: ObjectRef
    response_headers: tuple[tuple[str, str], ...] = ()


class SilverTable(Contract):
    caption: str | None = None
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


class SilverImage(Contract):
    url: str
    alt: str = ""
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    kind: str
    artifact_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    media_type: str | None = None
    extracted_text: str = ""
    extractor: str | None = None
    analysis_error: str | None = None


class SilverDocument(Contract):
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_url: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str | None = None
    metadata: tuple[tuple[str, tuple[str, ...]], ...] = ()
    json_ld: tuple[JsonValue, ...] = ()
    tables: tuple[SilverTable, ...] = ()
    lists: tuple[tuple[str, ...], ...] = ()
    images: tuple[SilverImage, ...] = ()
    text: str = ""

    def metadata_dict(self) -> dict[str, tuple[str, ...]]:
        return dict(self.metadata)


class FieldProfile(Contract):
    path: str
    document_count: int = Field(ge=1)
    frequency: float = Field(ge=0, le=1)
    observed_types: tuple[str, ...]
    examples: tuple[str, ...] = ()


class DiscoveredSchema(Contract):
    document_count: int = Field(ge=0)
    fields: tuple[FieldProfile, ...]


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list | tuple):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__
