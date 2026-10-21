"""Schema-constrained LLM normalization with evidence and deterministic IDs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, JsonValue

from .contracts import Contract, SilverDocument
from .models import (
    CanonicalEntity,
    EntityType,
    Evidence,
    FieldAssertion,
    NormalizationResult,
)


class CandidateEvidence(Contract):
    locator: str
    quote: str = Field(min_length=1, max_length=2_000)


class CandidateField(Contract):
    path: str
    value: JsonValue
    confidence: float = Field(ge=0, le=1)
    evidence: tuple[CandidateEvidence, ...] = Field(min_length=1)


class CandidateEntity(Contract):
    entity_type: EntityType
    natural_key: str = Field(min_length=1)
    fields: tuple[CandidateField, ...]


class CandidateExtraction(Contract):
    entities: tuple[CandidateEntity, ...]
    warnings: tuple[str, ...] = ()


class StructuredLLM(Protocol):
    model_name: str

    async def extract(
        self,
        *,
        system: str,
        document: str,
        json_schema: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class OpenAICompatibleLLM:
    """Small optional adapter for OpenAI-compatible chat completion endpoints."""

    def __init__(self, *, endpoint: str, api_key: str, model_name: str) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name

    async def extract(
        self,
        *,
        system: str,
        document: str,
        json_schema: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        try:
            import httpx
        except ModuleNotFoundError as error:  # pragma: no cover - optional dependency
            raise RuntimeError("install the 'llm' extra to use an HTTP LLM") from error
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": document},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "broadcast_metadata",
                    "strict": True,
                    "schema": dict(json_schema),
                },
            },
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.endpoint}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        content = body["choices"][0]["message"]["content"]
        value = json.loads(content)
        if not isinstance(value, Mapping):
            raise ValueError("LLM response must be a JSON object")
        return cast(Mapping[str, Any], value)


class MetadataNormalizer:
    def __init__(
        self,
        provider: StructuredLLM,
        *,
        schema_version: str = "1.0.0",
        prompt_version: str = "1",
        max_input_characters: int = 60_000,
    ) -> None:
        self.provider = provider
        self.schema_version = schema_version
        self.prompt_version = prompt_version
        self.max_input_characters = max_input_characters

    async def normalize(self, document: SilverDocument) -> NormalizationResult:
        source = self._render_document(document)
        raw = await self.provider.extract(
            system=(
                "Extract only broadcast metadata explicitly supported by the supplied "
                "document. Every field requires an exact quote. Do not infer missing facts."
            ),
            document=source[: self.max_input_characters],
            json_schema=CandidateExtraction.model_json_schema(),
        )
        candidate = CandidateExtraction.model_validate(raw)
        entities: list[CanonicalEntity] = []
        assertions: list[FieldAssertion] = []
        warnings = list(candidate.warnings)
        for item in candidate.entities:
            entity_id = uuid5(
                NAMESPACE_URL,
                f"{item.entity_type}:{item.natural_key.casefold().strip()}",
            )
            accepted: dict[str, JsonValue] = {}
            for field in item.fields:
                valid_evidence = tuple(
                    self._to_evidence(document, evidence)
                    for evidence in field.evidence
                    if evidence.quote in source
                )
                if not valid_evidence:
                    warnings.append(f"rejected unsupported field: {field.path}")
                    continue
                accepted[field.path] = field.value
                assertions.append(
                    FieldAssertion(
                        entity_id=entity_id,
                        field_path=field.path,
                        value=field.value,
                        confidence=field.confidence,
                        evidence=valid_evidence,
                        extractor_version="llm-normalizer/1",
                        model_name=self.provider.model_name,
                        prompt_version=self.prompt_version,
                    )
                )
            entities.append(
                CanonicalEntity(
                    entity_id=entity_id,
                    entity_type=item.entity_type,
                    natural_key=item.natural_key,
                    schema_version=self.schema_version,
                    attributes=accepted,
                    source_urls=(document.source_url,),
                )
            )
        return NormalizationResult(
            schema_version=self.schema_version,
            entities=tuple(entities),
            assertions=tuple(assertions),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _to_evidence(
        document: SilverDocument,
        evidence: CandidateEvidence,
    ) -> Evidence:
        for image in document.images:
            if (
                image.artifact_sha256 is not None
                and evidence.quote in image.extracted_text
            ):
                return Evidence(
                    source_url=image.url,
                    artifact_sha256=image.artifact_sha256,
                    locator=f"image:{image.url}",
                    quote=evidence.quote,
                )
        return Evidence(
            source_url=document.source_url,
            artifact_sha256=document.content_sha256,
            locator=evidence.locator,
            quote=evidence.quote,
        )

    @staticmethod
    def _render_document(document: SilverDocument) -> str:
        sections = [
            f"URL: {document.source_url}",
            f"TITLE: {document.title or ''}",
            "METADATA: " + json.dumps(dict(document.metadata), ensure_ascii=False),
            "JSON_LD: " + json.dumps(document.json_ld, ensure_ascii=False),
            "TABLES: "
            + json.dumps(
                [table.model_dump(mode="json") for table in document.tables],
                ensure_ascii=False,
            ),
            "IMAGES: "
            + json.dumps(
                [
                    image.model_dump(mode="json")
                    for image in document.images
                    if image.extracted_text
                ],
                ensure_ascii=False,
            ),
            f"TEXT: {document.text}",
        ]
        return "\n".join(sections)
