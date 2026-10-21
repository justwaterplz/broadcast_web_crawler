"""Shared naming for readable, collision-safe collection folders."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))


def safe_folder_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")[:60].rstrip(" .")
    if not name:
        name = "제목없음"
    if re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", name.split(".")[0], re.I):
        name = "_" + name
    return name


def create_run_folder(root: Path, category: str, subcategory: str, now: datetime) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    stamp = now.astimezone(KST).strftime("%Y%m%d_%H%M%S_%f")
    base = f"{stamp}_{safe_folder_name(category)}_{safe_folder_name(subcategory)}"
    for suffix in range(1000):
        path = root / (base if suffix == 0 else f"{base}_{suffix + 1}")
        try:
            path.mkdir()
            return path
        except FileExistsError:
            continue
    raise RuntimeError("Unable to create a unique run folder")
