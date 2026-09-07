from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))

import nl_brief  # noqa: E402


class NlBriefTests(unittest.TestCase):
    def test_shared_and_diff_are_separate_paragraphs(self) -> None:
        text = nl_brief.for_shortlist([
            {
                "part_number": "STM32C591VGT6",
                "facts": {
                    "core": "Arm Cortex-M33",
                    "frequency_mhz": 144,
                    "flash_kb": 1024,
                    "usb": 1,
                },
            },
            {
                "part_number": "STM32C593VGT6",
                "facts": {
                    "core": "Arm Cortex-M33",
                    "frequency_mhz": 144,
                    "flash_kb": 1024,
                    "fdcan": 1,
                },
            },
        ])
        paras = text.split("\n\n")
        self.assertGreaterEqual(len(paras), 3)
        self.assertIn("Arm Cortex-M33", paras[0])
        self.assertIn("144 MHz", paras[0])
        self.assertIn("三颗之间的差别", paras[1])
        self.assertIn("STM32C591VGT6", paras[1])
        self.assertIn("不是设计签核", paras[-1])

    def test_compare_mentions_competitor_and_temp_gap(self) -> None:
        text = nl_brief.for_compare(
            {
                "manufacturer": "NXP",
                "part_number": "MK64FN1M0VLL12",
                "specs": {"frequency_mhz": 120, "temperature_max_c": 105},
                "source_note": "规格来自模型回忆，须核对厂家 datasheet。",
            },
            [{
                "part_number": "STM32C591VGT6",
                "facts": {"frequency_mhz": 144, "temperature_max_c": 85},
            }],
        )
        self.assertIn("MK64FN1M0VLL12", text)
        self.assertIn("短名单约高 1.2 倍", text)
        self.assertIn("低于竞品的 105 °C", text)

    def test_compare_says_clock_gap_in_times(self) -> None:
        text = nl_brief.for_compare(
            {
                "manufacturer": "GigaDevice",
                "part_number": "GD32H779",
                "specs": {"frequency_mhz": 600, "flash_kb": 4096},
                "series_prefix": ["STM32H5"],
                "application": "motor_control",
            },
            [{
                "part_number": "STM32H523CEU6",
                "facts": {"frequency_mhz": 250, "flash_kb": 512, "motor_timers": 1},
            }],
        )
        self.assertIn("主频差约 2.4 倍", text)
        self.assertIn("不是性能对等", text)
        self.assertIn("电机控制", text)

    def test_english_brief_uses_shortlist_wording(self) -> None:
        text = nl_brief.for_shortlist(
            [{
                "part_number": "STM32C591VGT6",
                "facts": {"core": "Arm Cortex-M33", "frequency_mhz": 144},
            }],
            lang="en",
        )
        self.assertIn("STM32C591VGT6", text)
        self.assertIn("shortlist", text.lower())
        self.assertIn("design sign-off", text)
        self.assertNotIn("当前短名单", text)
        self.assertNotIn("不是设计签核", text)


if __name__ == "__main__":
    unittest.main()
