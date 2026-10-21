"""PostgreSQL-oriented SQLAlchemy persistence with SQLite test compatibility."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from .contracts import CrawlRun
from .models import NormalizationResult, ReviewItem

metadata = MetaData()
json_type = JSON().with_variant(JSONB(), "postgresql")

crawl_runs = Table(
    "crawl_run",
    metadata,
    Column("run_id", String(36), primary_key=True),
    Column("start_url", Text, nullable=False),
    Column("phase", String(32), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("payload", json_type, nullable=False),
)

entities = Table(
    "canonical_entity",
    metadata,
    Column("entity_id", String(36), primary_key=True),
    Column("entity_type", String(32), nullable=False, index=True),
    Column("natural_key", Text, nullable=False),
    Column("schema_version", String(32), nullable=False),
    Column("payload", json_type, nullable=False),
    UniqueConstraint("entity_type", "natural_key", name="uq_entity_natural_key"),
)

assertions = Table(
    "field_assertion",
    metadata,
    Column("assertion_id", String(36), primary_key=True),
    Column(
        "entity_id",
        String(36),
        ForeignKey("canonical_entity.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("run_id", String(36), nullable=False, index=True),
    Column("field_path", Text, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("payload", json_type, nullable=False),
)

review_items = Table(
    "review_item",
    metadata,
    Column("review_id", String(36), primary_key=True),
    Column("run_id", String(36), nullable=False, index=True),
    Column("reason", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", json_type, nullable=False),
)


class MetadataRepository:
    def __init__(self, database_url: str, *, engine: Engine | None = None) -> None:
        self.engine = engine or create_engine(database_url)

    def create_schema(self) -> None:
        metadata.create_all(self.engine)

    def save_run(self, run: CrawlRun) -> None:
        values = {
            "run_id": str(run.run_id),
            "start_url": run.start_url,
            "phase": run.phase.value,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "payload": run.model_dump(mode="json"),
        }
        with self.engine.begin() as connection:
            exists = connection.execute(
                select(crawl_runs.c.run_id).where(crawl_runs.c.run_id == str(run.run_id))
            ).first()
            if exists:
                connection.execute(
                    update(crawl_runs)
                    .where(crawl_runs.c.run_id == str(run.run_id))
                    .values(**values)
                )
            else:
                connection.execute(insert(crawl_runs).values(**values))

    def get_run(self, run_id: UUID) -> CrawlRun | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(crawl_runs.c.payload).where(crawl_runs.c.run_id == str(run_id))
            ).scalar_one_or_none()
        return CrawlRun.model_validate(row) if row is not None else None

    def save_result(
        self,
        run_id: UUID,
        result: NormalizationResult,
        *,
        review_threshold: float = 0.7,
    ) -> tuple[ReviewItem, ...]:
        reviews: list[ReviewItem] = []
        with self.engine.begin() as connection:
            for entity in result.entities:
                payload = entity.model_dump(mode="json")
                values = {
                    "entity_id": str(entity.entity_id),
                    "entity_type": entity.entity_type.value,
                    "natural_key": entity.natural_key,
                    "schema_version": entity.schema_version,
                    "payload": payload,
                }
                exists = connection.execute(
                    select(entities.c.entity_id).where(
                        entities.c.entity_id == str(entity.entity_id)
                    )
                ).first()
                if exists:
                    connection.execute(
                        update(entities)
                        .where(entities.c.entity_id == str(entity.entity_id))
                        .values(**values)
                    )
                else:
                    connection.execute(insert(entities).values(**values))
            for assertion in result.assertions:
                assertion_exists = connection.execute(
                    select(assertions.c.assertion_id).where(
                        assertions.c.assertion_id == str(assertion.assertion_id)
                    )
                ).first()
                if not assertion_exists:
                    connection.execute(
                        insert(assertions).values(
                            assertion_id=str(assertion.assertion_id),
                            entity_id=str(assertion.entity_id),
                            run_id=str(run_id),
                            field_path=assertion.field_path,
                            confidence=assertion.confidence,
                            payload=assertion.model_dump(mode="json"),
                        )
                    )
                if assertion.confidence < review_threshold and not assertion_exists:
                    review = ReviewItem(
                        run_id=run_id,
                        assertion=assertion,
                        reason=f"confidence below {review_threshold:.2f}",
                    )
                    reviews.append(review)
                    connection.execute(
                        insert(review_items).values(
                            review_id=str(review.review_id),
                            run_id=str(run_id),
                            reason=review.reason,
                            created_at=review.created_at,
                            payload=review.model_dump(mode="json"),
                        )
                    )
        return tuple(reviews)

    def list_entities(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            return list(connection.execute(select(entities.c.payload)).scalars())

    def replace_reviews(self, run_id: UUID, items: Iterable[ReviewItem]) -> None:
        with self.engine.begin() as connection:
            connection.execute(delete(review_items).where(review_items.c.run_id == str(run_id)))
            for item in items:
                connection.execute(
                    insert(review_items).values(
                        review_id=str(item.review_id),
                        run_id=str(run_id),
                        reason=item.reason,
                        created_at=item.created_at,
                        payload=item.model_dump(mode="json"),
                    )
                )
