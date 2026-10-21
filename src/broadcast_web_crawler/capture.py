"""Capture hooks that persist crawler output into immutable manifests."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from .contracts import (
    CapturedImage,
    CapturedResource,
    CaptureManifest,
    ObjectRef,
    PageCapture,
)
from .crawler import CrawlOutput, ResponseCapture
from .storage import LocalObjectStore
from .urls import canonicalize_url


class LocalCaptureSession:
    """Persist response bodies and finalize a deterministic capture manifest."""

    def __init__(self, store: LocalObjectStore) -> None:
        self.store = store
        self._resources: defaultdict[str, list[CapturedResource]] = defaultdict(list)

    async def __call__(self, capture: ResponseCapture) -> None:
        headers = dict(capture.headers)
        media_type = headers.get("content-type", "application/octet-stream").split(";", 1)[0]
        reference = self.store.put_bytes(capture.body, media_type=media_type)
        owner = canonicalize_url(capture.page_url) or capture.page_url
        self._resources[owner].append(
            CapturedResource(
                url=capture.url,
                status=capture.status,
                object=reference,
                headers=capture.headers,
                kind=capture.resource_type,
            )
        )

    def finalize(
        self,
        output: CrawlOutput,
        *,
        run_id: UUID,
        captured_at: datetime | None = None,
    ) -> tuple[CaptureManifest, ObjectRef]:
        pages: list[PageCapture] = []
        for page in output.pages:
            html = self.store.put_bytes(page.html, media_type="text/html")
            resources = tuple(
                sorted(
                    self._resources.get(page.url, ()),
                    key=lambda resource: (
                        resource.url,
                        resource.status,
                        resource.object.sha256,
                    ),
                )
            )
            resource_objects = {
                resource.url: resource.object
                for resource in resources
                if resource.kind == "image"
            }
            images = tuple(
                CapturedImage(
                    url=image.url,
                    alt=image.alt,
                    width=image.width,
                    height=image.height,
                    kind=image.kind,
                    object=resource_objects.get(image.url),
                )
                for image in page.images
            )
            pages.append(
                PageCapture(
                    url=page.url,
                    depth=page.depth,
                    score=page.score,
                    html=html,
                    resources=resources,
                    images=images,
                    links=page.links,
                )
            )
        manifest = CaptureManifest(
            run_id=run_id,
            start_url=output.start_url,
            captured_at=captured_at or datetime.now(UTC),
            pages=tuple(pages),
            total_bytes=output.total_bytes,
        )
        return manifest, self.store.put_manifest(manifest)
