"""Immutable content-addressed local object storage."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .contracts import CaptureManifest, ObjectRef


class IntegrityError(RuntimeError):
    """Raised when an object does not match its content address."""


class LocalObjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = self.root / "objects" / "sha256"

    def _path(self, digest: str) -> Path:
        return self.objects / digest[:2] / digest[2:4] / digest

    def put_bytes(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
    ) -> ObjectRef:
        digest = hashlib.sha256(data).hexdigest()
        target = self._path(digest)
        if target.exists():
            if target.stat().st_size != len(data) or target.read_bytes() != data:
                raise IntegrityError(f"object collision or corruption: {digest}")
            return ObjectRef(sha256=digest, size=len(data), media_type=media_type)

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                temporary = handle.name
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if target.exists():
                Path(temporary).unlink(missing_ok=True)
            else:
                os.replace(temporary, target)
            temporary = None
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
        return ObjectRef(sha256=digest, size=len(data), media_type=media_type)

    def put_json(
        self,
        value: BaseModel | Any,
        *,
        media_type: str = "application/json",
    ) -> ObjectRef:
        serializable = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        payload = json.dumps(
            serializable,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return self.put_bytes(payload, media_type=media_type)

    def put_manifest(self, manifest: CaptureManifest) -> ObjectRef:
        return self.put_json(
            manifest,
            media_type="application/vnd.broadcast-crawler.capture+json",
        )

    def get_bytes(self, reference: ObjectRef, *, verify: bool = True) -> bytes:
        data = self._path(reference.sha256).read_bytes()
        if len(data) != reference.size:
            raise IntegrityError(f"size mismatch for {reference.sha256}")
        if verify and hashlib.sha256(data).hexdigest() != reference.sha256:
            raise IntegrityError(f"digest mismatch for {reference.sha256}")
        return data

    def exists(self, reference: ObjectRef) -> bool:
        return self._path(reference.sha256).is_file()
