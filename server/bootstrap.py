from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import uvicorn

import engine_adapter
import readiness

if str(engine_adapter.ENGINE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(engine_adapter.ENGINE_SCRIPTS))
import db_cache
import db_refresh

DEFAULT_DB_URL = "https://sw-center.st.com/packs/cube-finder-db/cube-finder-db.zip"


def configured_database() -> Path:
    explicit = os.environ.get("ST_MCU_DB")
    if explicit:
        return Path(explicit).expanduser().resolve()
    data_dir = Path(os.environ.get("ST_MCU_DATA_DIR", "/data")).expanduser().resolve()
    return data_dir / "cube-finder-db.db"


def ensure_database() -> db_cache.CacheResult:
    database = configured_database()
    mode = os.environ.get("ST_MCU_AUTO_UPDATE", "if_missing").strip().lower()
    result = db_cache.ensure(
        database,
        url=os.environ.get("ST_MCU_DB_URL", DEFAULT_DB_URL),
        mode=mode,
    )
    os.environ["ST_MCU_DB"] = str(result.database)
    return result


def _load_database() -> None:
    try:
        result = ensure_database()
        readiness.mark_ready(result.as_dict())
        print(
            "Database ready: "
            f"source={result.source} stale={result.stale} fingerprint={result.fingerprint}",
            flush=True,
        )
    except Exception as exc:
        readiness.mark_error(exc)
        print(f"Database startup failed: {exc}", file=sys.stderr)
        return
    # One extra HEAD so /api/health can answer "are we current?" from the first request
    # onwards, instead of staying blank until the first periodic check fires.
    db_refresh.probe_upstream()
    db_refresh.start(on_reload=readiness.mark_ready)


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
