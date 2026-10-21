"""Field-frequency schema discovery over deterministic Silver documents."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from .contracts import DiscoveredSchema, FieldProfile, SilverDocument, json_type


def _flatten(value: Any, path: str, output: dict[str, list[Any]]) -> None:
    if isinstance(value, Mapping):
        if path:
            output[path].append(value)
        for key in sorted(value, key=str):
            child = f"{path}.{key}" if path else str(key)
            _flatten(value[key], child, output)
        return
    if isinstance(value, list | tuple):
        if path:
            output[path].append(value)
        for item in value:
            _flatten(item, f"{path}[]", output)
        return
    output[path].append(value)


def _example(value: Any) -> str:
    if isinstance(value, str):
        return value[:120]
    rendered = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return rendered[:120]


def discover_schema(
    documents: Iterable[SilverDocument],
    *,
    min_frequency: float = 0.0,
    max_examples: int = 3,
) -> DiscoveredSchema:
    if not 0 <= min_frequency <= 1:
        raise ValueError("min_frequency must be between 0 and 1")
    if max_examples < 0:
        raise ValueError("max_examples cannot be negative")

    docs = tuple(documents)
    occurrences: defaultdict[str, int] = defaultdict(int)
    types: defaultdict[str, set[str]] = defaultdict(set)
    examples: defaultdict[str, set[str]] = defaultdict(set)

    for document in docs:
        metadata = {key: list(values) for key, values in document.metadata}
        payload: dict[str, Any] = {
            "title": document.title,
            "metadata": metadata,
            "json_ld": list(document.json_ld),
            "tables": [table.model_dump(mode="python") for table in document.tables],
            "lists": [list(items) for items in document.lists],
            "images": [
                image.model_dump(mode="python") for image in document.images
            ],
            "text": document.text,
        }
        flattened: defaultdict[str, list[Any]] = defaultdict(list)
        _flatten(payload, "", flattened)
        for path, values in flattened.items():
            if not path or all(value is None or value == "" for value in values):
                continue
            occurrences[path] += 1
            types[path].update(json_type(value) for value in values)
            examples[path].update(
                _example(value) for value in values if value is not None and value != ""
            )

    count = len(docs)
    profiles = tuple(
        FieldProfile(
            path=path,
            document_count=occurrences[path],
            frequency=occurrences[path] / count,
            observed_types=tuple(sorted(types[path])),
            examples=tuple(sorted(examples[path]))[:max_examples],
        )
        for path in sorted(occurrences)
        if count and occurrences[path] / count >= min_frequency
    )
    return DiscoveredSchema(document_count=count, fields=profiles)
