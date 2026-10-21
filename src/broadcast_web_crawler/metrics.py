"""Quality gates for extraction evaluation and production monitoring."""

from __future__ import annotations

from collections import Counter

from pydantic import Field

from .contracts import Contract
from .models import NormalizationResult


class QualityReport(Contract):
    entity_count: int = Field(ge=0)
    assertion_count: int = Field(ge=0)
    evidence_coverage: float = Field(ge=0, le=1)
    mean_confidence: float = Field(ge=0, le=1)
    review_rate: float = Field(ge=0, le=1)
    fields: dict[str, int]
    warning_count: int = Field(ge=0)


def quality_report(
    result: NormalizationResult,
    *,
    review_threshold: float = 0.7,
) -> QualityReport:
    assertions = result.assertions
    count = len(assertions)
    with_evidence = sum(bool(assertion.evidence) for assertion in assertions)
    review_count = sum(assertion.confidence < review_threshold for assertion in assertions)
    confidence = sum(assertion.confidence for assertion in assertions)
    return QualityReport(
        entity_count=len(result.entities),
        assertion_count=count,
        evidence_coverage=with_evidence / count if count else 1.0,
        mean_confidence=confidence / count if count else 1.0,
        review_rate=review_count / count if count else 0.0,
        fields=dict(Counter(assertion.field_path for assertion in assertions)),
        warning_count=len(result.warnings),
    )
