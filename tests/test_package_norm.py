from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))

import mcu_recommender as engine  # noqa: E402
import package_norm  # noqa: E402


class PackageNormTests(unittest.TestCase):
    def test_families(self) -> None:
        self.assertEqual(package_norm.canonical_package("UFQFPN 48 4x4x0.6 mm"), "QFN")
        self.assertEqual(package_norm.canonical_package("VFQFPN"), "QFN")
        self.assertEqual(package_norm.canonical_package("UFBGA 64 5x5x0.6"), "BGA")
        self.assertEqual(package_norm.canonical_package("LQFP 64 10x10x1.4 mm"), "LQFP")
        self.assertEqual(package_norm.canonical_package("EWLCSP66"), "WLCSP")
        self.assertTrue(package_norm.package_matches("UFQFPN", ["QFN"]))
        self.assertTrue(package_norm.package_matches("UFBGA", ["BGA"]))
        self.assertFalse(package_norm.package_matches("LQFP", ["QFN"]))

    def test_constraint_accepts_st_qfn_names(self) -> None:
        status, _ = engine.evaluate_constraint("package_type", "UFQFPN", ["QFN"])
        self.assertEqual(status, "pass")
        status, _ = engine.evaluate_constraint("package_type", "LQFP", ["QFN"])
        self.assertEqual(status, "fail")
        status, _ = engine.evaluate_constraint("pin_count", 48, {"min": 64, "max": 64})
        self.assertEqual(status, "fail")
        status, _ = engine.evaluate_constraint("pin_count", 64, {"min": 64, "max": 64})
        self.assertEqual(status, "pass")
        status, _ = engine.evaluate_constraint("pin_count", 48, {"max": 64})
        self.assertEqual(status, "pass")


if __name__ == "__main__":
    unittest.main()
