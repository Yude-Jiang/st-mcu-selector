from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))

import object_store  # noqa: E402


class AtomicInstallTests(unittest.TestCase):
    def test_replace_leaves_no_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "cube-finder-db.db"
            dest.write_bytes(b"old")
            object_store.install_atomically(dest, lambda path: path.write_bytes(b"new"))
            self.assertEqual(dest.read_bytes(), b"new")
            leftovers = [path for path in Path(tmp).iterdir() if path.name.startswith(".")]
            self.assertEqual(leftovers, [])

    def test_failed_write_keeps_dest(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "cube-finder-db.db"
            dest.write_bytes(b"old")

            def boom(path: Path) -> None:
                path.write_bytes(b"partial")
                raise OSError("disk")

            with self.assertRaises(OSError):
                object_store.install_atomically(dest, boom)
            self.assertEqual(dest.read_bytes(), b"old")
            leftovers = [path for path in Path(tmp).iterdir() if path.name.startswith(".")]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
