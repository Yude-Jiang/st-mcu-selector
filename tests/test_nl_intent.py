from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))
os.chdir(ROOT)

import nl_intent  # noqa: E402


class NlIntentTests(unittest.TestCase):
    def test_extract_h5_from_prefer_series(self) -> None:
        text = "有没有跟GD32H779 性能接近的MCU，最好是从H5中找"
        self.assertEqual(nl_intent.extract_series_prefix(text), ["STM32H5"])

    def test_extract_named_stm32_series(self) -> None:
        self.assertEqual(nl_intent.extract_series_prefix("优先 STM32G4"), ["STM32G4"])

    def test_sanitize_drops_invented_st_part(self) -> None:
        clean = nl_intent.sanitize({
            "intent": "compare",
            "competitor": {"manufacturer": "ST", "part_number": "STM32H563RIT6"},
            "series_prefix": "H5",
            "must": {"price": 1, "usb": {"min": 1}},
        })
        self.assertEqual(clean["intent"], "recommend")
        self.assertIsNone(clean["competitor"])
        self.assertEqual(clean["series_prefix"], ["STM32H5"])
        self.assertEqual(clean["must"]["usb"], {"min": 1})
        self.assertNotIn("price", clean["must"])


if __name__ == "__main__":
    unittest.main()
