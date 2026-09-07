from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))

import app_fit  # noqa: E402
import nl_contrast  # noqa: E402


class ContrastAndFitTests(unittest.TestCase):
    def test_clock_ratio_uses_times(self) -> None:
        line = nl_contrast.contrast_line("frequency_mhz", 250, 600, "zh")
        self.assertIn("主频差约 2.4 倍", line)
        self.assertIn("600", line)
        self.assertIn("250", line)

    def test_english_clock_ratio(self) -> None:
        line = nl_contrast.contrast_line("frequency_mhz", 250, 600, "en")
        self.assertIn("2.4×", line)
        self.assertIn("Clock", line)

    def test_named_series_flags_non_peer(self) -> None:
        gap = nl_contrast.series_gap_line(
            {"specs": {"frequency_mhz": 600}},
            [{"facts": {"frequency_mhz": 250}}],
            ["STM32H5"],
            "zh",
        )
        self.assertIn("不是性能对等", gap)

    def test_injects_ratio_when_model_omits_it(self) -> None:
        text = nl_contrast.ensure_ratio_talk(
            "对照 GD32H779，短名单是 STM32H523CEU6。",
            {"specs": {"frequency_mhz": 600}, "series_prefix": ["STM32H5"]},
            [{"part_number": "STM32H523CEU6", "facts": {"frequency_mhz": 250}}],
            "zh",
        )
        self.assertIn("主频差约 2.4 倍", text)
        self.assertIn("不是性能对等", text)

    def test_motor_note_lists_present_and_missing(self) -> None:
        note = app_fit.judge_item(
            {"motor_timers": 1, "adc_channels": 16},
            "motor_control",
            "zh",
        )
        self.assertIn("电机控制", note)
        self.assertIn("电机定时器", note)
        self.assertIn("HRTIM", note)

    def test_st_email_rule_matches_gate_js(self) -> None:
        js = (ROOT / "web" / "gate.js").read_text(encoding="utf-8")
        self.assertIn('email.includes("@st.com")', js)
        self.assertTrue(self._is_st_email("yude.jiang@st.com"))
        self.assertTrue(self._is_st_email("name@st.com.cn"))
        self.assertFalse(self._is_st_email("foo@gmail.com"))
        self.assertFalse(self._is_st_email("not-an-email"))

    @staticmethod
    def _is_st_email(value: str) -> bool:
        email = str(value or "").strip().lower()
        import re
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            return False
        return "@st.com" in email


if __name__ == "__main__":
    unittest.main()
