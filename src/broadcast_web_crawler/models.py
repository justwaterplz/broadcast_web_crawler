"""Versioned canonical metadata and field-level provenance contracts."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from .contracts import Contract, _utc_now


class EntityType(StrEnum):
    PROGRAM = "program"
    SEASON = "season"
    EPISODE = "episode"
    PERSON = "person"
    ORGANIZATION = "organization"
    CREDIT = "credit"
    BROADCAST_EVENT = "broadcast_event"
    PRODUCTION_EVENT = "production_event"
    ASSET = "asset"


class Precision(StrEnum):
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    TIME = "time"
    RANGE = "range"
    UNKNOWN = "unknown"


class TemporalValue(Contract):
    start: date | datetime | None = None
    end: date | datetime | None = None
    precision: Precision = Precision.UNKNOWN
    certainty: float = Field(default=1.0, ge=0, le=1)
    raw_text: str

    @model_validator(mode="after")
    def validate_range(self) -> TemporalValue:
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("temporal start must not be after end")
        return self


class Evidence(Contract):
    source_url: str
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: str
    quote: str = Field(min_length=1, max_length=2_000)
    observed_at: AwareDatetime = Field(default_factory=_utc_now)


class FieldAssertion(Contract):
    assertion_id: UUID = Field(default_factory=uuid4)
    entity_id: UUID
    field_path: str = Field(min_length=1)
    value: JsonValue
    confidence: float = Field(ge=0, le=1)
    evidence: tuple[Evidence, ...] = Field(min_length=1)
    extractor_version: str
    model_name: str | None = None
    prompt_version: str | None = None


class CanonicalEntity(Contract):
    entity_id: UUID = Field(default_factory=uuid4)
    entity_type: EntityType
    natural_key: str = Field(min_length=1)
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    source_urls: tuple[str, ...] = ()
    created_at: AwareDatetime = Field(default_factory=_utc_now)


class EntityRelation(Contract):
    source_id: UUID
    predicate: str
    target_id: UUID
    attributes: dict[str, JsonValue] = Field(default_factory=dict)


class NormalizationResult(Contract):
    schema_version: str
    entities: tuple[CanonicalEntity, ...]
    assertions: tuple[FieldAssertion, ...]
    relations: tuple[EntityRelation, ...] = ()
    warnings: tuple[str, ...] = ()


class ReviewItem(Contract):
    review_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    assertion: FieldAssertion
    reason: str
    created_at: AwareDatetime = Field(default_factory=_utc_now)
