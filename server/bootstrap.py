from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import uvicorn

import engine_adapter
import readiness


def configured_database() -> Path:
    explicit = os.environ.get("ST_MCU_DB")
    if explicit:
        return Path(explicit).expanduser().resolve()
    data_dir = Path(os.environ.get("ST_MCU_DATA_DIR", "/data")).expanduser().resolve()
    return data_dir / "cube-finder-db.db"


def ensure_database() -> Path:
    database = configured_database()
    mode = os.environ.get("ST_MCU_AUTO_UPDATE", "if_missing").strip().lower()
    if mode not in {"never", "if_missing", "always"}:
        raise ValueError("ST_MCU_AUTO_UPDATE must be never, if_missing, or always")
    should_update = mode == "always" or (mode == "if_missing" and not database.is_file())
    if should_update:
        database.parent.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(engine_adapter.ENGINE_SCRIPTS / "update_database.py"),
            "--output-dir",
            str(database.parent),
            "--url",
            os.environ.get(
                "ST_MCU_DB_URL",
                "https://sw-center.st.com/packs/cube-finder-db/cube-finder-db.zip",
            ),
        ]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError:
            if not database.is_file():
                raise
            print(
                "Database update failed; continuing with the existing validated database.",
                file=sys.stderr,
            )
    if not database.is_file():
        raise FileNotFoundError(
            f"Database is missing: {database}. Enable ST_MCU_AUTO_UPDATE or mount a database file."
        )
    os.environ["ST_MCU_DB"] = str(database)
    engine_adapter.validate_database(database)
    return database


def _load_database() -> None:
    try:
        ensure_database()
        readiness.mark_ready()
    except Exception as exc:
        readiness.mark_error(exc)
        print(f"Database startup failed: {exc}", file=sys.stderr)


def main() -> None:
    threading.Thread(target=_load_database, daemon=True, name="st-mcu-db-init").start()
    uvicorn.run(
        "app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        log_level=os.environ.get("LOG_LEVEL", "info"),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "*"),
    )


if __name__ == "__main__":
    main()
