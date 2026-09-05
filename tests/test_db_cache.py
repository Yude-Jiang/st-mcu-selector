from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "engine"))
sys.path.insert(0, str(ROOT / "tests"))

import db_cache  # noqa: E402
import update_database as updater  # noqa: E402
from memory_store import MemoryObjectStore  # noqa: E402

URL = "https://sw-center.st.com/packs/cube-finder-db/cube-finder-db.zip"


def write_mini_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            "CREATE TABLE cpn (id INTEGER);"
            "CREATE TABLE rpn (id INTEGER);"
            "CREATE TABLE attribute (id INTEGER);"
            "CREATE TABLE version (id INTEGER);"
        )
        connection.commit()
    finally:
        connection.close()


def remote_meta(etag: str) -> dict[str, str | None]:
    return {
        "url": URL,
        "etag": etag,
        "last_modified": "Sat, 01 Jan 2026 00:00:00 GMT",
        "content_length": None,
        "content_type": "application/zip",
    }


class DbCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.database = self.data_dir / "cube-finder-db.db"
        self.store = MemoryObjectStore()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _install(self, etag: str, digest: str):
        def fake_install(url: str, output_dir: Path, *, force: bool = False) -> dict:
            write_mini_db(Path(output_dir) / "cube-finder-db.db")
            return {
                "url": url,
                "etag": etag,
                "sha256": digest,
                "fingerprint": updater.fingerprint({"etag": etag}),
                "updated_at": "2026-01-01T00:00:00+00:00",
                "skipped": False,
            }

        return fake_install

    def test_oss_hit_skips_st_download(self) -> None:
        write_mini_db(self.database)
        key = "cube-finder-db/objects/aaa/cube-finder-db.db"
        self.store.upload_from(key, self.database)
        self.database.unlink()
        self.store.write_json(
            "cube-finder-db/current.json",
            {
                "url": URL,
                "etag": '"v1"',
                "fingerprint": 'etag:"v1"',
                "sha256": "aaa",
                "object": key,
            },
        )
        with patch.object(updater, "metadata", return_value=remote_meta('"v1"')):
            with patch.object(updater, "install_from_url") as install:
                result = db_cache.ensure(
                    self.database, url=URL, mode="if_missing", store=self.store, bucket="test"
                )
        install.assert_not_called()
        self.assertEqual(result.source, "cache")
        self.assertFalse(result.stale)
        self.assertTrue(self.database.is_file())

    def test_etag_change_writes_new_object_keeps_old(self) -> None:
        write_mini_db(self.database)
        old_key = "cube-finder-db/objects/aaa/cube-finder-db.db"
        self.store.upload_from(old_key, self.database)
        self.store.write_json(
            "cube-finder-db/current.json",
            {
                "url": URL,
                "etag": '"v1"',
                "fingerprint": 'etag:"v1"',
                "sha256": "aaa",
                "object": old_key,
            },
        )
        with patch.object(updater, "metadata", return_value=remote_meta('"v2"')):
            with patch.object(updater, "install_from_url", side_effect=self._install('"v2"', "bbb")):
                result = db_cache.ensure(
                    self.database, url=URL, mode="if_missing", store=self.store, bucket="test"
                )
        new_key = "cube-finder-db/objects/bbb/cube-finder-db.db"
        self.assertEqual(result.source, "st")
        self.assertTrue(self.store.exists(old_key))
        self.assertTrue(self.store.exists(new_key))
        pointer = self.store.read_json("cube-finder-db/current.json")
        assert pointer is not None
        self.assertEqual(pointer["object"], new_key)

    def test_st_unreachable_uses_oss_and_marks_stale(self) -> None:
        write_mini_db(self.database)
        key = "cube-finder-db/objects/aaa/cube-finder-db.db"
        self.store.upload_from(key, self.database)
        self.database.unlink()
        self.store.write_json(
            "cube-finder-db/current.json",
            {
                "url": URL,
                "etag": '"v1"',
                "fingerprint": 'etag:"v1"',
                "sha256": "aaa",
                "object": key,
            },
        )
        with patch.object(updater, "metadata", side_effect=URLError("down")):
            with patch.object(updater, "install_from_url") as install:
                result = db_cache.ensure(
                    self.database, url=URL, mode="if_missing", store=self.store, bucket="test"
                )
        install.assert_not_called()
        self.assertEqual(result.source, "cache")
        self.assertTrue(result.stale)

    def test_st_refresh_failure_falls_back_to_previous_oss(self) -> None:
        write_mini_db(self.database)
        key = "cube-finder-db/objects/aaa/cube-finder-db.db"
        self.store.upload_from(key, self.database)
        self.store.write_json(
            "cube-finder-db/current.json",
            {
                "url": URL,
                "etag": '"v1"',
                "fingerprint": 'etag:"v1"',
                "sha256": "aaa",
                "object": key,
            },
        )
        with patch.object(updater, "metadata", return_value=remote_meta('"v2"')):
            with patch.object(updater, "install_from_url", side_effect=RuntimeError("bad zip")):
                result = db_cache.ensure(
                    self.database, url=URL, mode="if_missing", store=self.store, bucket="test"
                )
        self.assertEqual(result.source, "cache")
        self.assertTrue(result.stale)
        pointer = self.store.read_json("cube-finder-db/current.json")
        assert pointer is not None
        self.assertEqual(pointer["object"], key)

    def test_fingerprint_prefers_etag(self) -> None:
        value = updater.fingerprint({"etag": '"abc"', "last_modified": "x", "content_length": 1})
        self.assertEqual(value, 'etag:"abc"')

    def test_rejects_both_gcs_and_oss_env(self) -> None:
        env = {"ST_MCU_GCS_BUCKET": "gcs-db", "ST_MCU_OSS_BUCKET": "oss-db"}
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaises(ValueError) as ctx:
                db_cache.ensure(self.database, url=URL, mode="if_missing")
        self.assertIn("ST_MCU_GCS_BUCKET", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
