#!/usr/bin/env python3
"""Download and atomically install the public ST MCUFinder data bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_URL = "https://sw-center.st.com/packs/cube-finder-db/cube-finder-db.zip"
ARCHIVE_NAME = "cube-finder-db.zip"
DATABASE_NAME = "cube-finder-db.db"
STATE_NAME = ".cube-finder-db.state.json"
USER_AGENT = "Codex-ST-MCU-Recommender/0.1"


def web_request(url: str, method: str = "GET") -> urllib.request.Request:
    return urllib.request.Request(
        url, method=method, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )


def metadata(url: str) -> dict:
    with urllib.request.urlopen(web_request(url, "HEAD"), timeout=45) as response:
        return {
            "url": response.geturl(),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "content_length": int(response.headers.get("Content-Length", "0")) or None,
            "content_type": response.headers.get("Content-Type"),
        }


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def is_current(state: dict, remote: dict, archive: Path, database: Path) -> bool:
    if not archive.is_file() or not database.is_file():
        return False
    expected_size = remote.get("content_length")
    if expected_size and archive.stat().st_size != expected_size:
        return False
    return bool(
        state.get("etag")
        and state.get("etag") == remote.get("etag")
        and state.get("url") == remote.get("url")
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path) -> None:
    with urllib.request.urlopen(web_request(url), timeout=90) as response:
        expected = int(response.headers.get("Content-Length", "0"))
        received = 0
        with target.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                received += len(chunk)
                if expected:
                    print(
                        f"\rDownloading {received / 1024 / 1024:.1f} / "
                        f"{expected / 1024 / 1024:.1f} MiB",
                        end="",
                        flush=True,
                    )
        if expected and received != expected:
            raise RuntimeError(f"download size mismatch: expected={expected}, actual={received}")
        print()


def validate_and_extract(archive: Path, staging: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        bad_member = bundle.testzip()
        if bad_member:
            raise RuntimeError(f"ZIP CRC failed: {bad_member}")
        if DATABASE_NAME not in bundle.namelist():
            raise RuntimeError(f"ZIP does not contain {DATABASE_NAME}")
        for member in bundle.infolist():
            member_path = Path(member.filename.replace("\\", "/"))
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError(f"unsafe ZIP path: {member.filename}")
        bundle.extractall(staging)
    database = staging / DATABASE_NAME
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {result}")
    finally:
        connection.close()


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def install_tree(staging: Path, output_dir: Path) -> None:
    for source in staging.rglob("*"):
        if source.is_file():
            atomic_copy(source, output_dir / source.relative_to(staging))


def fingerprint(remote: dict) -> str:
    etag = (remote.get("etag") or "").strip()
    if etag:
        return f"etag:{etag}"
    last_modified = remote.get("last_modified") or ""
    content_length = remote.get("content_length") or ""
    if last_modified or content_length:
        return f"meta:{last_modified}|{content_length}"
    return ""


def install_from_url(url: str, output_dir: Path, *, force: bool = False) -> dict:
    output_dir = output_dir.resolve()
    archive = output_dir / ARCHIVE_NAME
    database = output_dir / DATABASE_NAME
    state_path = output_dir / STATE_NAME
    remote = metadata(url)
    current = is_current(load_state(state_path), remote, archive, database)
    if current and not force:
        state = load_state(state_path)
        return {**remote, **state, "skipped": True}
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="st-mcu-db-") as temp_name:
        temp_dir = Path(temp_name)
        temp_archive = temp_dir / ARCHIVE_NAME
        staging = temp_dir / "extracted"
        staging.mkdir()
        download(url, temp_archive)
        validate_and_extract(temp_archive, staging)
        digest = sha256(temp_archive)
        install_tree(staging, output_dir)
        atomic_copy(temp_archive, archive)
    state = {
        **remote,
        "sha256": digest,
        "fingerprint": fingerprint(remote),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "skipped": False,
    }
    temp_state = output_dir / f"{STATE_NAME}.tmp"
    temp_state.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_state, state_path)
    print(f"Database updated: {database}")
    print(f"SHA-256: {digest}")
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Update the ST MCU recommendation database")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / ".st-mcu-recommender" / "data",
    )
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    try:
        remote = metadata(args.url)
        current = is_current(
            load_state(output_dir / STATE_NAME),
            remote,
            output_dir / ARCHIVE_NAME,
            output_dir / DATABASE_NAME,
        )
        print(json.dumps({**remote, "local_current": current}, ensure_ascii=False, indent=2))
        if args.check_only:
            return 0
        if current and not args.force:
            print(f"Database is current: {output_dir / DATABASE_NAME}")
            return 0
        install_from_url(args.url, output_dir, force=args.force)
        return 0
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
