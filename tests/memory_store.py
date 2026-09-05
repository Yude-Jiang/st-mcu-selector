from __future__ import annotations

from pathlib import Path
from typing import Any


class MemoryObjectStore:
    def __init__(self) -> None:
        self.json_objects: dict[str, dict[str, Any]] = {}
        self.files: dict[str, bytes] = {}

    def read_json(self, key: str) -> dict[str, Any] | None:
        payload = self.json_objects.get(key)
        return None if payload is None else dict(payload)

    def write_json(self, key: str, payload: dict[str, Any]) -> None:
        self.json_objects[key] = dict(payload)

    def exists(self, key: str) -> bool:
        return key in self.json_objects or key in self.files

    def download_to(self, key: str, dest: Path) -> None:
        if key not in self.files:
            raise FileNotFoundError(f"OSS object missing: {key}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.files[key])

    def upload_from(self, key: str, src: Path) -> None:
        self.files[key] = src.read_bytes()
