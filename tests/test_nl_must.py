from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))
os.chdir(ROOT)

import nl_must  # noqa: E402


class NlMustTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)

    def test_rules_extract_motor_sentence(self) -> None:
        result = nl_must.parse_requirements("电机控制，主频至少 170 MHz，LQFP64，要 FDCAN")
        self.assertEqual(result["source"], "rules")
        self.assertEqual(result["application"], "motor_control")
        self.assertEqual(result["must"]["frequency_mhz"], {"min": 170})
        self.assertEqual(result["must"]["package_type"], ["LQFP"])
        self.assertEqual(result["must"]["pin_count"], {"min": 64, "max": 64})
        self.assertEqual(result["must"]["fdcan"], {"min": 1})

    def test_ignores_price_and_requires_real_specs(self) -> None:
        with self.assertRaises(ValueError):
            nl_must.parse_requirements("只要便宜、交期短")

    def test_model_overlay_is_sanitized(self) -> None:
        fake = {
            "application": "motor_control",
            "must": {
                "frequency_mhz": {"min": 170},
                "price": 1,
                "package_type": ["LQFP"],
            },
            "notes": ["忽略价格"],
        }
        with patch.object(nl_must, "call_model", return_value=fake):
            os.environ["DEEPSEEK_API_KEY"] = "test"
            result = nl_must.parse_requirements("电机 170MHz LQFP")
        self.assertEqual(result["source"], "model")
        self.assertNotIn("price", result["must"])
        self.assertEqual(result["must"]["frequency_mhz"], {"min": 170})

    def test_vite_named_secret_counts_as_configured(self) -> None:
        os.environ["VITE_DEEPSEEK_API_KEY"] = "test"
        self.assertTrue(nl_must.llm_configured())
        self.assertEqual(nl_must.llm_api_key(), "test")

    def test_i2c_count_and_compact_package(self) -> None:
        text = "我想找一颗STM32，具备3路I2C，封装尽量小，价格尽量便宜"
        result = nl_must.parse_with_rules(text)
        self.assertEqual(result["must"]["i2c"], {"min": 3})
        self.assertTrue(result["compact_package"])
        self.assertTrue(any("已忽略价格" in note for note in result["notes"]))
        self.assertNotIn("package_type", result["must"])

    def test_i2c_is_not_a_temperature(self) -> None:
        must = nl_must.parse_with_rules("电机控制，要 I2C 和 USB")["must"]
        self.assertNotIn("temperature_max_c", must)
        self.assertEqual(must.get("usb"), {"min": 1})

    def test_stm32c_part_is_not_a_temperature(self) -> None:
        must = nl_must.parse_with_rules("查看 STM32C011F6P6，LQFP")["must"]
        self.assertNotIn("temperature_max_c", must)
        self.assertEqual(must.get("package_type"), ["LQFP"])

    def test_celsius_still_extracted(self) -> None:
        self.assertEqual(
            nl_must.parse_with_rules("工业级 105°C，LQFP64")["must"]["temperature_max_c"],
            {"min": 105},
        )
        self.assertEqual(
            nl_must.parse_with_rules("工作温度 105 度")["must"]["temperature_max_c"],
            {"min": 105},
        )
        self.assertEqual(
            nl_must.parse_with_rules("耐温 105C")["must"]["temperature_max_c"],
            {"min": 105},
        )
        self.assertEqual(
            nl_must.parse_with_rules("LQFP64 105C")["must"]["temperature_max_c"],
            {"min": 105},
        )

    def test_qfn_aliases_and_pin_budget(self) -> None:
        must = nl_must.parse_with_rules("电机控制 UFQFPN48")["must"]
        self.assertEqual(must["package_type"], ["QFN"])
        self.assertEqual(must["pin_count"], {"min": 48, "max": 48})
        budget = nl_must.parse_with_rules("LQFP，不超过 64 脚")["must"]
        self.assertEqual(budget["package_type"], ["LQFP"])
        self.assertEqual(budget["pin_count"], {"max": 64})
        self.assertNotIn("pin_count", nl_must.parse_with_rules("Flash 512KB，LQFP")["must"])

    def test_rules_keep_package_when_model_guesses_wrong(self) -> None:
        rules = nl_must.parse_with_rules("LQFP64")
        fake = {"must": {"package_type": ["BGA"], "pin_count": {"max": 100}}}
        merged = nl_must.merge_drafts(rules, fake)
        self.assertEqual(merged["must"]["package_type"], ["LQFP"])
        self.assertEqual(merged["must"]["pin_count"], {"min": 64, "max": 64})


if __name__ == "__main__":
    unittest.main()
