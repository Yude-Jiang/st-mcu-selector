from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))
os.chdir(ROOT)

import nl_turn  # noqa: E402


class NlTurnTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)
        self.candidates = [
            {
                "part_number": "STM32G474RET3",
                "score": 91,
                "facts": {"frequency_mhz": 170, "flash_kb": 512, "usb": 1},
                "matches": ["主频满足"],
                "risks": [],
            },
            {
                "part_number": "STM32G431RBT6",
                "score": 80,
                "facts": {"frequency_mhz": 170, "flash_kb": 128},
                "matches": [],
                "risks": [],
            },
        ]

    def test_followup_explains_current_three(self) -> None:
        result = nl_turn.handle("为什么是这三颗？", {"flash_kb": {"min": 128}}, "motor_control", "allow_risk", self.candidates, [])
        self.assertEqual(result["intent"], "explain")
        self.assertIn("STM32G474RET3", result["answer"])
        self.assertFalse(result["rerecommend"])

    def test_followup_refuses_price(self) -> None:
        result = nl_turn.handle("哪颗更便宜、交期短？", {}, None, "allow_risk", self.candidates, [])
        self.assertEqual(result["intent"], "refuse")
        self.assertFalse(result["rerecommend"])

    def test_new_usb_constraint_is_refine(self) -> None:
        result = nl_turn.handle("再加 USB", {"flash_kb": {"min": 128}}, None, "allow_risk", self.candidates, [])
        self.assertEqual(result["intent"], "refine_must")
        self.assertEqual(result["must"]["usb"], {"min": 1})
        self.assertEqual(result["must"]["flash_kb"], {"min": 128})
        self.assertTrue(result["rerecommend"])

    def test_vague_question_clarifies_without_nxp_example(self) -> None:
        result = nl_turn.handle("帮我看看", {}, None, "allow_risk", [], [])
        self.assertEqual(result["intent"], "explain")
        self.assertFalse(result["rerecommend"])
        self.assertIn("还不够检索", result["answer"])
        self.assertNotIn("MK64", result["answer"])
        self.assertNotIn("NXP", result["answer"])

    def test_datasheet_forces_compare_without_recall(self) -> None:
        result = nl_turn.handle(
            "对照这颗",
            {},
            None,
            "allow_risk",
            [],
            [],
            datasheet={
                "specs": {"frequency_mhz": 600, "flash_kb": 4096, "package_type": "BGA"},
                "part_number": "GD32H779",
                "manufacturer": "GigaDevice",
                "source_note": "规格来自用户上传的 datasheet 摘录（shot.png，未保存文件）。",
            },
        )
        self.assertEqual(result["intent"], "compare")
        self.assertEqual(result["source"], "rules")
        self.assertEqual(result["compare"]["part_number"], "GD32H779")
        self.assertEqual(result["compare"]["specs"]["frequency_mhz"], 600)


if __name__ == "__main__":
    unittest.main()
