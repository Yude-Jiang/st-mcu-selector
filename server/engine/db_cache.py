from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError

import engine_adapter
import update_database as updater
from object_store import GcsObjectStore, ObjectStore, OssObjectStore

DATABASE_NAME = updater.DATABASE_NAME
POINTER_NAME = "current.json"


@dataclass
class CacheResult:
    database: Path
    source: str
    fingerprint: str | None
    stale: bool
    object_key: str | None = None
    etag: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source": self.source,
            "stale": self.stale,
        }
        if self.fingerprint:
            payload["fingerprint"] = self.fingerprint
        if self.etag:
            payload["etag"] = self.etag
        if self.object_key:
            payload["object"] = self.object_key
        return payload


def _prefix() -> str:
    for key in ("ST_MCU_GCS_PREFIX", "ST_MCU_OSS_PREFIX"):
        value = os.environ.get(key, "").strip().strip("/")
        if value:
            return value
    return "cube-finder-db"


def _store_source(store: ObjectStore) -> str:
    name = type(store).__name__
    if name == "GcsObjectStore":
        return "gcs"
    if name == "OssObjectStore":
        return "oss"
    return "cache"


def _pointer_key() -> str:
    return f"{_prefix()}/{POINTER_NAME}"


def _object_key(sha256: str) -> str:
    return f"{_prefix()}/objects/{sha256}/{DATABASE_NAME}"


def _probe_remote(url: str) -> dict[str, Any] | None:
    try:
        return updater.metadata(url)
    except (URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"ST database HEAD failed; will use object-cache/local fallback: {exc}", flush=True)
        return None


def _materialize(store: ObjectStore, pointer: dict[str, Any], database: Path) -> None:
    key = str(pointer.get("object") or "")
    if not key:
        raise FileNotFoundError("Cache pointer is missing object key")
    store.download_to(key, database)
    engine_adapter.validate_database(database)


def _publish(store: ObjectStore, database: Path, url: str, state: dict[str, Any]) -> dict[str, Any]:
    digest = str(state["sha256"])
    key = _object_key(digest)
    if not store.exists(key):
        store.upload_from(key, database)
    pointer = {
        "url": url,
        "etag": state.get("etag"),
        "last_modified": state.get("last_modified"),
        "content_length": state.get("content_length"),
        "fingerprint": state.get("fingerprint") or updater.fingerprint(state),
        "sha256": digest,
        "object": key,
        "updated_at": state.get("updated_at"),
    }
    store.write_json(_pointer_key(), pointer)
    return pointer


def _refresh_from_st(url: str, database: Path, store: ObjectStore | None) -> CacheResult:
    state = updater.install_from_url(url, database.parent, force=True)
    engine_adapter.validate_database(database)
    pointer = _publish(store, database, url, state) if store is not None else None
    return CacheResult(
        database=database,
        source="st",
        fingerprint=state.get("fingerprint") or updater.fingerprint(state),
        stale=False,
        object_key=None if pointer is None else str(pointer["object"]),
        etag=state.get("etag"),
    )


def _from_pointer(store: ObjectStore, pointer: dict[str, Any], database: Path, *, stale: bool) -> CacheResult:
    _materialize(store, pointer, database)
    print(
        f"Database loaded from {_store_source(store)} object={pointer.get('object')} stale={stale}",
        flush=True,
    )
    return CacheResult(
        database=database,
        source=_store_source(store),
        fingerprint=pointer.get("fingerprint"),
        stale=stale,
        object_key=pointer.get("object"),
        etag=pointer.get("etag"),
    )


def _ensure_with_store(database: Path, url: str, mode: str, store: ObjectStore) -> CacheResult:
    database.parent.mkdir(parents=True, exist_ok=True)
    pointer = store.read_json(_pointer_key())
    if mode == "never":
        if pointer:
            return _from_pointer(store, pointer, database, stale=False)
        if database.is_file():
            engine_adapter.validate_database(database)
            return CacheResult(database, "local", None, False)
        raise FileNotFoundError("ST_MCU_AUTO_UPDATE=never and cache pointer is missing.")

    remote = _probe_remote(url)
    if remote and pointer:
        same = (
            pointer.get("fingerprint") == updater.fingerprint(remote)
            and pointer.get("url") == url
        )
        if same and store.exists(str(pointer.get("object") or "")):
            return _from_pointer(store, pointer, database, stale=False)

    if remote:
        try:
            return _refresh_from_st(url, database, store)
        except (URLError, TimeoutError, OSError, RuntimeError) as exc:
            print(f"ST database refresh failed: {exc}", flush=True)
            if pointer:
                return _from_pointer(store, pointer, database, stale=True)
            raise

    if pointer:
        return _from_pointer(store, pointer, database, stale=True)
    if database.is_file():
        engine_adapter.validate_database(database)
        return CacheResult(database, "local", None, True)
    raise FileNotFoundError(
        "器件库不可用：ST 源无法访问，且对象缓存没有可用副本。"
    )


def _ensure_local(database: Path, url: str, mode: str) -> CacheResult:
    database.parent.mkdir(parents=True, exist_ok=True)
    if mode == "never":
        if not database.is_file():
            raise FileNotFoundError(f"Database is missing: {database}")
        engine_adapter.validate_database(database)
        return CacheResult(database, "local", None, False)
    should_update = mode == "always" or not database.is_file()
    if should_update:
        try:
            return _refresh_from_st(url, database, None)
        except (URLError, TimeoutError, OSError, RuntimeError):
            if not database.is_file():
                raise
            print(
                "Database update failed; continuing with the existing validated database.",
                flush=True,
            )
    if not database.is_file():
        raise FileNotFoundError(f"Database is missing: {database}")
    engine_adapter.validate_database(database)
    return CacheResult(database, "local", None, False)


def ensure(
    database: Path,
    *,
    url: str,
    mode: str,
    store: ObjectStore | None = None,
    bucket: str | None = None,
) -> CacheResult:
    if mode not in {"never", "if_missing", "always"}:
        raise ValueError("ST_MCU_AUTO_UPDATE must be never, if_missing, or always")
    gcs_bucket = os.environ.get("ST_MCU_GCS_BUCKET", "").strip()
    oss_bucket = os.environ.get("ST_MCU_OSS_BUCKET", "").strip()
    if store is not None:
        return _ensure_with_store(database, url, mode, store)
    if gcs_bucket and oss_bucket:
        raise ValueError("Set only one of ST_MCU_GCS_BUCKET or ST_MCU_OSS_BUCKET")
    if gcs_bucket:
        return _ensure_with_store(database, url, mode, GcsObjectStore(gcs_bucket))
    if oss_bucket:
        return _ensure_with_store(database, url, mode, OssObjectStore(oss_bucket))
    return _ensure_local(database, url, mode)
