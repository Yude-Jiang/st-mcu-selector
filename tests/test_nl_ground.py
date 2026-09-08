from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "server", ROOT / "server" / "engine"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import nl_ground  # noqa: E402

SHORTLIST = [
    {
        "part_number": "STM32G474RET6",
        "score": 92.5,
        "facts": {"frequency_mhz": 170, "flash_kb": 512, "ram_kb": 128, "pin_count": 64},
    },
    {
        "part_number": "STM32G431CBT6",
        "score": 88.0,
        "facts": {"frequency_mhz": 170, "flash_kb": 128, "ram_kb": 32, "pin_count": 48},
    },
]


class InventedPartTest(unittest.TestCase):
    def test_listed_part_is_allowed(self):
        answer = "STM32G474RET6 的 Flash 更大。"
        self.assertFalse(nl_ground.invented_part(answer, SHORTLIST))

    def test_series_prefix_is_allowed(self):
        self.assertFalse(nl_ground.invented_part("三颗都在 STM32G4 系列内。", SHORTLIST))

    def test_part_outside_shortlist_is_invention(self):
        answer = "更适合的是 STM32H743ZIT6。"
        self.assertTrue(nl_ground.invented_part(answer, SHORTLIST))

    def test_any_part_is_invention_when_shortlist_empty(self):
        self.assertTrue(nl_ground.invented_part("试试 STM32F103C8T6。", []))


class GroundedNumberTest(unittest.TestCase):
    def setUp(self):
        self.allowed = nl_ground.payload_numbers(SHORTLIST)

    def test_number_from_facts_is_grounded(self):
        self.assertFalse(nl_ground.invented_number("主频 170 MHz。", self.allowed))

    def test_ranks_need_no_source(self):
        self.assertFalse(nl_ground.invented_number("第 2 颗是 3 个里最省的。", self.allowed))

    def test_kb_restated_as_mb_is_grounded(self):
        # 512 KB quoted as 0.5 MB is the same retrieved value, not a new claim.
        self.assertFalse(nl_ground.invented_number("Flash 0.5 MB。", self.allowed))

    def test_unsourced_figure_is_invention(self):
        # CoreMark never appears in the shortlist, so neither may a CoreMark number.
        self.assertTrue(nl_ground.invented_number("CoreMark 约 550 分。", self.allowed))

    def test_wrong_spec_value_is_invention(self):
        self.assertTrue(nl_ground.invented_number("主频可到 480 MHz。", self.allowed))

    def test_part_number_digits_do_not_license_numbers(self):
        # STM32G474RET6 must not donate 474 to the whitelist, or a nearby invented
        # "480 MHz" would slip through inside the tolerance band.
        self.assertNotIn(474.0, self.allowed)
        self.assertIn(170.0, self.allowed)

    def test_package_name_digits_do_not_license_numbers(self):
        allowed = nl_ground.payload_numbers([{"facts": {"package": "LQFP100"}}])
        self.assertEqual(allowed, set())


class EnforceTest(unittest.TestCase):
    def test_grounded_prose_survives(self):
        answer = "STM32G474RET6 主频 170 MHz，Flash 512 KB。"
        self.assertEqual(
            nl_ground.enforce(answer, "FALLBACK", SHORTLIST, SHORTLIST),
            answer,
        )

    def test_invented_part_falls_back(self):
        answer = "建议改用 STM32H743ZIT6。"
        self.assertEqual(
            nl_ground.enforce(answer, "FALLBACK", SHORTLIST, SHORTLIST),
            "FALLBACK",
        )

    def test_invented_number_falls_back(self):
        answer = "STM32G474RET6 的以太网速率 100 Mbps。"
        self.assertEqual(
            nl_ground.enforce(answer, "FALLBACK", SHORTLIST, SHORTLIST),
            "FALLBACK",
        )

    def test_empty_answer_falls_back(self):
        self.assertEqual(nl_ground.enforce("", "FALLBACK", SHORTLIST, SHORTLIST), "FALLBACK")


class ExplainIsGroundedTest(unittest.TestCase):
    """The prose the page shows is checked against retrieval before it reaches a user."""

    def setUp(self):
        import os
        from unittest.mock import patch

        import nl_brief
        import nl_must
        import nl_turn

        self.patch = patch
        self.nl_must = nl_must
        self.nl_turn = nl_turn
        os.environ["DEEPSEEK_API_KEY"] = "test"
        self.addCleanup(os.environ.pop, "DEEPSEEK_API_KEY", None)
        self.deterministic = nl_brief.for_shortlist(SHORTLIST)

    def _explain(self, answer: str) -> str:
        with self.patch.object(self.nl_must, "complete_json", return_value={"answer": answer}):
            return self.nl_turn.explain("这三颗有什么差别", SHORTLIST, [])

    def test_invented_part_is_replaced_by_the_deterministic_brief(self):
        self.assertEqual(self._explain("建议改用 STM32H743ZIT6。"), self.deterministic)

    def test_unsourced_figure_is_replaced(self):
        self.assertEqual(self._explain("CoreMark 约 550 分。"), self.deterministic)

    def test_wrong_spec_value_is_replaced(self):
        self.assertEqual(self._explain("主频可到 480 MHz。"), self.deterministic)

    def test_faithful_prose_reaches_the_user(self):
        answer = "STM32G474RET6 主频 170 MHz，Flash 512 KB，比 STM32G431CBT6 更大。"
        self.assertEqual(self._explain(answer), answer)


if __name__ == "__main__":
    unittest.main()
