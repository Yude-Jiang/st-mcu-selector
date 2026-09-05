from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "server" / "engine"
sys.path.insert(0, str(ENGINE))
os.chdir(ROOT)

from shortlist import diversify_by_series, series_group  # noqa: E402
import mcu_recommender as engine  # noqa: E402


class ShortlistTests(unittest.TestCase):
    def test_series_group_strips_package_suffix(self) -> None:
        self.assertEqual(series_group("STM32H503CBT6", "STM32H503CB"), "STM32H503")
        self.assertEqual(series_group("STM32H503EBY6TR", "STM32H503EB"), "STM32H503")
        self.assertEqual(series_group("STM32G474RET3", "STM32G474RE"), "STM32G474")
        self.assertEqual(series_group("STM32L4R5ZIT6", "STM32L4R5ZI"), "STM32L4R5")
        self.assertEqual(series_group("STM32WBA52CEU6", "STM32WBA52CE"), "STM32WBA52")

    def test_diversify_keeps_one_part_per_series(self) -> None:
        ranked = [
            _item("STM32H503CBT6", "STM32H503CB", "LQFP48", 48),
            _item("STM32H503EBY6TR", "STM32H503EB", "WLCSP25", 25),
            _item("STM32H503KBU6", "STM32H503KB", "UFQFPN32", 32),
            _item("STM32G474RET3", "STM32G474RE", "LQFP64", 64),
            _item("STM32H743VIT6", "STM32H743VI", "LQFP100", 100),
        ]
        picked = diversify_by_series(ranked, 3)
        self.assertEqual(
            [item["part_number"] for item in picked],
            ["STM32H503CBT6", "STM32G474RET3", "STM32H743VIT6"],
        )
        extras = " ".join(picked[0]["other_packages"])
        self.assertIn("WLCSP25", extras)
        self.assertIn("UFQFPN32", extras)
        self.assertEqual(picked[1]["other_packages"], [])

    def test_constraint_copy_uses_chinese_labels(self) -> None:
        status, detail = engine.evaluate_constraint("frequency_mhz", 250, {"min": 170})
        self.assertEqual(status, "pass")
        self.assertIn("主频", detail)
        self.assertNotIn("frequency_mhz", detail)

    def test_compare_copy_uses_chinese_labels(self) -> None:
        closeness, detail = engine.similarity("flash_kb", 512, 512)
        self.assertEqual(closeness, 1.0)
        self.assertIn("Flash", detail)
        self.assertIn("竞品", detail)
        self.assertNotIn("competitor", detail)


def _item(part: str, rpn: str, package: str, pins: int) -> dict:
    return {
        "part_number": part,
        "rpn": rpn,
        "facts": {"package": package, "pin_count": pins},
    }


if __name__ == "__main__":
    unittest.main()
