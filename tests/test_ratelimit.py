from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "server", ROOT / "server" / "engine"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from middleware.budget import MAX_TRACKED_CLIENTS, WINDOW_SECONDS, Budget  # noqa: E402


class BudgetTest(unittest.TestCase):
    def test_allows_up_to_the_limit(self):
        budget = Budget(limit=3)
        for index in range(3):
            allowed, _ = budget.allow("a", 100.0 + index)
            self.assertTrue(allowed, f"hit {index} should pass")

    def test_refuses_past_the_limit(self):
        budget = Budget(limit=2)
        budget.allow("a", 100.0)
        budget.allow("a", 100.5)
        allowed, retry = budget.allow("a", 101.0)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry, 1)

    def test_window_slides(self):
        budget = Budget(limit=2)
        budget.allow("a", 100.0)
        budget.allow("a", 101.0)
        self.assertFalse(budget.allow("a", 102.0)[0])
        # Once the first two hits age out of the window the caller is served again.
        allowed, _ = budget.allow("a", 100.0 + WINDOW_SECONDS + 1.0)
        self.assertTrue(allowed)

    def test_keys_are_independent(self):
        budget = Budget(limit=1)
        self.assertTrue(budget.allow("a", 100.0)[0])
        self.assertFalse(budget.allow("a", 100.1)[0])
        self.assertTrue(budget.allow("b", 100.2)[0])

    def test_tracked_keys_stay_bounded(self):
        budget = Budget(limit=1)
        for index in range(5000):
            budget.allow(f"client-{index}", 100.0 + index)
        self.assertLessEqual(budget.tracked(), MAX_TRACKED_CLIENTS)


class PathClassTest(unittest.TestCase):
    """Path sets only; importing the middleware itself would pull in FastAPI."""

    def setUp(self):
        try:
            from middleware import ratelimit
        except ImportError:  # pragma: no cover - exercised only without FastAPI installed
            self.skipTest("fastapi not installed")
        self.ratelimit = ratelimit

    def test_costly_and_cheap_paths_are_disjoint(self):
        self.assertFalse(self.ratelimit.COSTLY_PATHS & self.ratelimit.CHEAP_PATHS)
        self.assertFalse(self.ratelimit.COSTLY_PATHS & self.ratelimit.EXEMPT_PATHS)
        # Health probes must never be throttled or Cloud Run marks the revision unhealthy.
        self.assertIn("/healthz", self.ratelimit.EXEMPT_PATHS)

    def test_llm_endpoints_are_costly(self):
        for path in ("/api/turn", "/api/parse-requirements", "/api/parse-datasheet"):
            self.assertIn(path, self.ratelimit.COSTLY_PATHS)


if __name__ == "__main__":
    unittest.main()
