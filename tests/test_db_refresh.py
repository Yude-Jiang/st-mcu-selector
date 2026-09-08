from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "server", ROOT / "server" / "engine"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import db_refresh  # noqa: E402


class IntervalTest(unittest.TestCase):
    def test_default_is_weekly(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("ST_MCU_DB_CHECK_INTERVAL_HOURS", None)
            self.assertEqual(db_refresh.interval_hours(), 168.0)

    def test_zero_disables(self):
        with patch.dict("os.environ", {"ST_MCU_DB_CHECK_INTERVAL_HOURS": "0"}):
            self.assertEqual(db_refresh.interval_hours(), 0.0)
            self.assertIsNone(db_refresh.start())

    def test_unparsable_falls_back_to_default(self):
        with patch.dict("os.environ", {"ST_MCU_DB_CHECK_INTERVAL_HOURS": "soon"}):
            self.assertEqual(db_refresh.interval_hours(), 168.0)


class ProbeTest(unittest.TestCase):
    def setUp(self):
        db_refresh.reset_for_tests()
        self.addCleanup(db_refresh.reset_for_tests)

    def test_probe_records_upstream_fingerprint(self):
        with patch.object(db_refresh.updater, "metadata", return_value={"etag": '"abc"'}):
            self.assertEqual(db_refresh.probe_upstream(), 'etag:"abc"')
        snap = db_refresh.snapshot('etag:"abc"')
        self.assertTrue(snap["up_to_date"])
        self.assertIn("checked_at", snap)

    def test_probe_marks_drift(self):
        with patch.object(db_refresh.updater, "metadata", return_value={"etag": '"new"'}):
            db_refresh.probe_upstream()
        snap = db_refresh.snapshot('etag:"old"')
        self.assertFalse(snap["up_to_date"])

    def test_probe_failure_is_recorded_not_raised(self):
        with patch.object(db_refresh.updater, "metadata", side_effect=OSError("dns")):
            self.assertIsNone(db_refresh.probe_upstream())
        snap = db_refresh.snapshot('etag:"old"')
        self.assertIn("check_error", snap)
        # Unknown upstream must not be reported as either current or behind.
        self.assertNotIn("up_to_date", snap)

    def test_snapshot_never_calls_the_network(self):
        with patch.object(db_refresh.updater, "metadata") as metadata:
            db_refresh.snapshot('etag:"old"')
        metadata.assert_not_called()


class RefreshOnceTest(unittest.TestCase):
    def setUp(self):
        db_refresh.reset_for_tests()
        self.addCleanup(db_refresh.reset_for_tests)

    def test_probe_failure_leaves_the_database_alone(self):
        calls: list[int] = []
        with patch.object(db_refresh.updater, "metadata", side_effect=OSError("dns")):
            outcome = db_refresh.refresh_once(reload_fn=lambda: calls.append(1))
        self.assertEqual(calls, [], "a failed probe must not touch the database")
        self.assertFalse(outcome["reloaded"])
        self.assertEqual(outcome["reason"], "probe_failed")

    def test_reload_failure_keeps_serving(self):
        def explode():
            raise RuntimeError("boom")

        with patch.object(db_refresh.updater, "metadata", return_value={"etag": '"new"'}):
            outcome = db_refresh.refresh_once(reload_fn=explode)
        self.assertFalse(outcome["reloaded"])
        self.assertEqual(outcome["reason"], "reload_failed")

    def test_successful_refresh_notifies_the_caller(self):
        class Result:
            def as_dict(self):
                return {"source": "st", "stale": False, "fingerprint": 'etag:"new"'}

        seen: list[dict] = []
        with patch.object(db_refresh.updater, "metadata", return_value={"etag": '"new"'}):
            outcome = db_refresh.refresh_once(
                on_reload=seen.append,
                reload_fn=Result,
                loaded_fingerprint='etag:"old"',
            )
        self.assertTrue(outcome["reloaded"])
        self.assertEqual(seen, [{"source": "st", "stale": False, "fingerprint": 'etag:"new"'}])

    def test_same_fingerprint_does_not_reload(self):
        calls: list[int] = []
        seen: list[dict] = []

        def reload():
            calls.append(1)
            raise AssertionError("must not run")

        with patch.object(db_refresh.updater, "metadata", return_value={"etag": '"abc"'}):
            outcome = db_refresh.refresh_once(
                on_reload=seen.append,
                reload_fn=reload,
                loaded_fingerprint='etag:"abc"',
            )
        self.assertEqual(calls, [])
        self.assertEqual(seen, [])
        self.assertFalse(outcome["reloaded"])
        self.assertEqual(outcome["reason"], "already_current")

    def test_reload_that_keeps_the_old_fingerprint_is_a_noop(self):
        class Same:
            def as_dict(self):
                return {"source": "local", "stale": False, "fingerprint": 'etag:"old"'}

        seen: list[dict] = []
        with patch.object(db_refresh.updater, "metadata", return_value={"etag": '"new"'}):
            outcome = db_refresh.refresh_once(
                on_reload=seen.append,
                reload_fn=Same,
                loaded_fingerprint='etag:"old"',
            )
        self.assertFalse(outcome["reloaded"])
        self.assertEqual(outcome["reason"], "reload_noop")
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
