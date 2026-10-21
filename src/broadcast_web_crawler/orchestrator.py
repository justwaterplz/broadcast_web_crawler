"""Idempotent URL-in pipeline orchestration."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from uuid import UUID

from pydantic import Field

from .capture import LocalCaptureSession
from .contracts import Contract, CrawlPhase, CrawlRun, ObjectRef
from .crawler import PlaywrightCrawler
from .database import MetadataRepository
from .models import EntityRelation, FieldAssertion, NormalizationResult
from .normalization import MetadataNormalizer
from .parsing import parse_html
from .storage import LocalObjectStore
from .vision import ImageTextExtractor, VisionPolicy, analyze_images

logger = logging.getLogger(__name__)


class RunSummary(Contract):
    run: CrawlRun
    manifest: ObjectRef | None = None
    discovered_pages: int = Field(default=0, ge=0)
    program_pages: int = Field(default=0, ge=0)
    normalized_entities: int = Field(default=0, ge=0)
    review_items: int = Field(default=0, ge=0)


class Pipeline:
    def __init__(
        self,
        *,
        crawler: PlaywrightCrawler,
        store: LocalObjectStore,
        repository: MetadataRepository,
        normalizer: MetadataNormalizer,
        image_extractor: ImageTextExtractor | None = None,
        vision_policy: VisionPolicy | None = None,
    ) -> None:
        self.crawler = crawler
        self.store = store
        self.repository = repository
        self.normalizer = normalizer
        self.image_extractor = image_extractor
        self.vision_policy = vision_policy or VisionPolicy(enabled=False)
        self._image_text_cache: dict[str, str] = {}
        self._summaries: dict[UUID, RunSummary] = {}
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def submit(self, start_url: str) -> RunSummary:
        run = CrawlRun(start_url=start_url)
        summary = RunSummary(run=run)
        self._summaries[run.run_id] = summary
        self.repository.save_run(run)
        self._tasks[run.run_id] = asyncio.create_task(self._execute(run.run_id))
        return summary

    def get(self, run_id: UUID) -> RunSummary | None:
        return self._summaries.get(run_id)

    async def wait(self, run_id: UUID) -> RunSummary:
        task = self._tasks.get(run_id)
        if task is not None:
            await task
        summary = self.get(run_id)
        if summary is None:
            raise KeyError(run_id)
        return summary

    def _transition(self, summary: RunSummary, phase: CrawlPhase) -> RunSummary:
        changed = summary.model_copy(update={"run": summary.run.transition(phase)})
        self._summaries[summary.run.run_id] = changed
        self.repository.save_run(changed.run)
        logger.info(
            "crawl_transition",
            extra={"run_id": str(changed.run.run_id), "phase": phase.value},
        )
        return changed

    async def _execute(self, run_id: UUID) -> None:
        summary = self._summaries[run_id]
        try:
            summary = self._transition(summary, CrawlPhase.DISCOVERING)
            session = LocalCaptureSession(self.store)
            summary = self._transition(summary, CrawlPhase.CAPTURING)
            output = await self.crawler.crawl(summary.run.start_url, hooks=(session,))
            manifest, manifest_ref = session.finalize(output, run_id=run_id)
            summary = summary.model_copy(
                update={
                    "manifest": manifest_ref,
                    "discovered_pages": len(output.pages),
                    "program_pages": len(output.program_urls),
                }
            )
            self._summaries[run_id] = summary

            summary = self._transition(summary, CrawlPhase.PARSING)
            target_urls = set(output.program_urls)
            documents = []
            for page in manifest.pages:
                if target_urls and page.url not in target_urls:
                    continue
                document = parse_html(
                    self.store.get_bytes(page.html),
                    source_url=page.url,
                    content_sha256=page.html.sha256,
                )
                images = await analyze_images(
                    page.images,
                    store=self.store,
                    extractor=self.image_extractor,
                    policy=self.vision_policy,
                    cache=self._image_text_cache,
                )
                documents.append(document.model_copy(update={"images": images}))

            summary = self._transition(summary, CrawlPhase.EXTRACTING)
            results = [await self.normalizer.normalize(document) for document in documents]
            summary = self._transition(summary, CrawlPhase.VALIDATING)
            merged = self._merge(results)
            summary = self._transition(summary, CrawlPhase.LOADING)
            reviews = self.repository.save_result(run_id, merged)
            summary = summary.model_copy(
                update={
                    "normalized_entities": len(merged.entities),
                    "review_items": len(reviews),
                }
            )
            summary = self._transition(summary, CrawlPhase.COMPLETED)
            self._summaries[run_id] = summary
        except Exception as error:
            current = self._summaries[run_id]
            if current.run.phase not in {CrawlPhase.COMPLETED, CrawlPhase.FAILED}:
                failed = current.model_copy(
                    update={
                        "run": current.run.transition(
                            CrawlPhase.FAILED,
                            reason=f"{type(error).__name__}: {error}",
                        )
                    }
                )
                self._summaries[run_id] = failed
                self.repository.save_run(failed.run)
                logger.exception(
                    "crawl_failed",
                    extra={"run_id": str(run_id), "phase": current.run.phase.value},
                )

    @staticmethod
    def _merge(results: list[NormalizationResult]) -> NormalizationResult:
        entities = {}
        assertions: list[FieldAssertion] = []
        relations: list[EntityRelation] = []
        warnings: list[str] = []
        schema_version = "1.0.0"
        for result in results:
            schema_version = result.schema_version
            entities.update({entity.entity_id: entity for entity in result.entities})
            assertions.extend(result.assertions)
            relations.extend(result.relations)
            warnings.extend(result.warnings)
        return NormalizationResult(
            schema_version=schema_version,
            entities=tuple(entities.values()),
            assertions=tuple(assertions),
            relations=tuple(relations),
            warnings=tuple(warnings),
        )


def local_data_path(root: str | Path) -> LocalObjectStore:
    return LocalObjectStore(Path(root))
