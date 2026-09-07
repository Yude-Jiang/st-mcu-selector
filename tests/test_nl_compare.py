from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))
os.chdir(ROOT)

import nl_compare  # noqa: E402
import nl_must  # noqa: E402
import nl_turn  # noqa: E402


class NlCompareTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)

    def test_parse_nxp_sentence(self) -> None:
        draft = nl_compare.parse_competitor(
            "对照 NXP MK64FN1M0VLL12，主频 120 MHz，Flash 1MB，LQFP100，来源 datasheet Rev 3"
        )
        self.assertEqual(draft["manufacturer"], "NXP")
        self.assertEqual(draft["part_number"], "MK64FN1M0VLL12")
        self.assertEqual(draft["specs"]["frequency_mhz"], 120)
        self.assertEqual(draft["specs"]["flash_kb"], 1024)
        self.assertEqual(draft["specs"]["package_type"], "LQFP")
        self.assertIn("datasheet", draft["source_note"].lower())

    def test_compare_intent_without_shortlist(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)
        result = nl_turn.handle(
            "对照 NXP MK64FN1M0VLL12，主频 120 MHz，Flash 512 KB，来源 datasheet",
            {},
            None,
            "allow_risk",
            [],
            [],
        )
        self.assertEqual(result["intent"], "compare")
        self.assertEqual(result["compare"]["part_number"], "MK64FN1M0VLL12")

    def test_part_only_needs_deepseek_or_specs(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)
        with self.assertRaises(ValueError):
            nl_compare.parse_competitor("替换 NXP MK64FN1M0VLL12")

    def test_part_only_uses_model_specs(self) -> None:
        fake = {
            "manufacturer": "NXP",
            "specs": {"frequency_mhz": 120, "flash_kb": 1024, "pin_count": 100, "package_type": "LQFP", "price": 9},
            "notes": ["回忆规格"],
        }
        with patch.object(nl_must, "complete_json", return_value=fake):
            os.environ["DEEPSEEK_API_KEY"] = "test"
            try:
                draft = nl_compare.parse_competitor("替换 NXP MK64FN1M0VLL12")
            finally:
                os.environ.pop("DEEPSEEK_API_KEY", None)
        self.assertEqual(draft["part_number"], "MK64FN1M0VLL12")
        self.assertEqual(draft["specs"]["frequency_mhz"], 120)
        self.assertEqual(draft["specs"]["flash_kb"], 1024)
        self.assertNotIn("price", draft["specs"])
        self.assertTrue(draft["recalled_specs"])
        self.assertIn("frequency_mhz", draft["essential"])


if __name__ == "__main__":
    unittest.main()
