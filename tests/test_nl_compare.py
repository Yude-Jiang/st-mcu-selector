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

    def test_part_only_is_refused(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)
        with self.assertRaises(nl_compare.NeedSpecs):
            nl_compare.parse_competitor("替换 NXP MK64FN1M0VLL12")

    def test_part_only_never_asks_the_model_for_specs(self) -> None:
        # Retrieval must not run on recalled numbers, so a bare part number is refused
        # even when DeepSeek is available rather than guessed at.
        with patch.object(nl_must, "complete_json") as complete:
            os.environ["DEEPSEEK_API_KEY"] = "test"
            try:
                with self.assertRaises(nl_compare.NeedSpecs):
                    nl_compare.parse_competitor("替换 NXP MK64FN1M0VLL12")
            finally:
                os.environ.pop("DEEPSEEK_API_KEY", None)
        complete.assert_not_called()

    def test_stated_specs_are_accepted(self) -> None:
        draft = nl_compare.parse_competitor("替换 NXP MK64FN1M0VLL12，主频 120MHz，Flash 1024KB")
        self.assertEqual(draft["part_number"], "MK64FN1M0VLL12")
        self.assertEqual(draft["specs"]["frequency_mhz"], 120)
        self.assertEqual(draft["specs"]["flash_kb"], 1024)
        self.assertIn("frequency_mhz", draft["essential"])

    def test_part_after_cjk_is_extracted(self) -> None:
        self.assertEqual(nl_compare._part_number("有没有跟GD32H779 性能接近的MCU"), "GD32H779")
        text = "有没有跟GD32H779 性能接近的MCU，最好是从H5中找"
        self.assertTrue(nl_compare.looks_like_compare(text))
        result = nl_turn.handle(text, {}, None, "allow_risk", [], [])
        self.assertEqual(result["series_prefix"], ["STM32H5"])
        self.assertEqual(result["intent"], "refine_must")
        self.assertTrue(result["rerecommend"])
        self.assertNotIn("MK64", result["answer"])

    def test_any_vendor_compare_uses_uploaded_specs(self) -> None:
        overlay = {
            "intent": "compare",
            "must": {},
            "series_prefix": ["STM32H5"],
            "competitor": {"manufacturer": "GigaDevice", "part_number": "GD32H779"},
            "inspect_part": None,
            "application": None,
            "notes": [],
            "source": "model",
        }
        sheet = {
            "specs": {"frequency_mhz": 600, "flash_kb": 4096},
            "part_number": "GD32H779",
            "manufacturer": "GigaDevice",
            "source_note": "规格来自用户上传的 datasheet 摘录（gd32h779.pdf，未保存文件）。",
        }
        with patch.object(nl_turn.nl_intent, "from_model", return_value=overlay):
            result = nl_turn.handle(
                "有没有跟GD32H779 性能接近的MCU，最好是从H5中找",
                {},
                None,
                "allow_risk",
                [],
                [],
                datasheet=sheet,
            )
        self.assertEqual(result["intent"], "compare")
        self.assertEqual(result["compare"]["part_number"], "GD32H779")
        self.assertEqual(result["compare"]["manufacturer"], "GigaDevice")
        self.assertEqual(result["compare"]["series_prefix"], ["STM32H5"])
        self.assertEqual(result["compare"]["specs"]["frequency_mhz"], 600)
        self.assertEqual(result["compare"]["essential"], [])

    def test_model_cannot_widen_named_series_to_h7(self) -> None:
        overlay = {
            "intent": "compare",
            "must": {},
            "series_prefix": ["STM32H7"],
            "competitor": {"manufacturer": "GigaDevice", "part_number": "GD32H779"},
            "inspect_part": None,
            "application": None,
            "notes": [],
            "source": "model",
        }
        sheet = {
            "specs": {"frequency_mhz": 550, "flash_kb": 3072},
            "part_number": "GD32H779",
            "manufacturer": "GigaDevice",
            "source_note": "规格来自用户上传的 datasheet 摘录（gd32h779.pdf，未保存文件）。",
        }
        with patch.object(nl_turn.nl_intent, "from_model", return_value=overlay):
            result = nl_turn.handle(
                "有没有跟GD32H779 性能接近的MCU，最好是从H5中找",
                {},
                None,
                "allow_risk",
                [],
                [],
                datasheet=sheet,
            )
        self.assertEqual(result["compare"]["series_prefix"], ["STM32H5"])
        self.assertNotIn("STM32H7", result["compare"]["series_prefix"])
        self.assertEqual(result["compare"]["essential"], [])

    def test_bare_part_without_specs_asks_for_the_datasheet(self) -> None:
        overlay = {
            "intent": "compare",
            "must": {},
            "series_prefix": [],
            "competitor": {"manufacturer": "GigaDevice", "part_number": "GD32H779"},
            "inspect_part": None,
            "application": None,
            "notes": [],
            "source": "model",
        }
        with patch.object(nl_turn.nl_intent, "from_model", return_value=overlay):
            result = nl_turn.handle("替换 GD32H779", {}, None, "allow_risk", [], [])
        self.assertEqual(result["intent"], "need_specs")
        self.assertNotIn("compare", result)
        self.assertIn("datasheet", result["answer"])

    def test_explain_compare_empty_does_not_invent_parts(self) -> None:
        answer = nl_compare.explain_compare(
            {"part_number": "GD32H779", "specs": {"frequency_mhz": 550}},
            {"recommendations": []},
        )
        self.assertNotIn("STM32H743", answer)
        self.assertNotIn("STM32H750", answer)
        self.assertIn("不能据此编造", answer)

    def test_explain_compare_empty_english(self) -> None:
        answer = nl_compare.explain_compare(
            {"part_number": "GD32H779"},
            {"recommendations": []},
            lang="en",
        )
        self.assertNotIn("STM32H743", answer)
        self.assertNotIn("短名单", answer)
        self.assertIn("will not invent", answer)

    def test_explain_compare_drops_invented_h7(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "test"
        try:
            with patch.object(
                nl_must,
                "complete_json",
                return_value={"answer": "建议 STM32H743、STM32H750 和 STM32H723。"},
            ):
                answer = nl_compare.explain_compare(
                    {"part_number": "GD32H779"},
                    {"recommendations": [{"part_number": "STM32H523CCT6", "facts": {}}]},
                )
        finally:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        self.assertNotIn("STM32H743", answer)
        self.assertIn("STM32H523CCT6", answer)


    def test_datasheet_skips_the_model(self) -> None:
        with patch.object(nl_must, "complete_json") as complete:
            draft = nl_compare.parse_competitor(
                "对照这颗竞品",
                datasheet={
                    "specs": {"frequency_mhz": 120, "flash_kb": 1024, "package_type": "LQFP", "price": 3},
                    "part_number": "MK64FN1M0VLL12",
                    "manufacturer": "NXP",
                    "source_note": "规格来自用户上传的 datasheet 摘录（mk64.pdf，未保存文件）。",
                },
            )
        complete.assert_not_called()
        self.assertEqual(draft["part_number"], "MK64FN1M0VLL12")
        self.assertEqual(draft["specs"]["frequency_mhz"], 120)
        self.assertNotIn("price", draft["specs"])

    def test_datasheet_without_part_uses_placeholder(self) -> None:
        draft = nl_compare.parse_competitor(
            "对照上传的规格书",
            datasheet={"specs": {"flash_kb": 512, "package_type": "QFN"}},
        )
        self.assertEqual(draft["part_number"], "DATASHEET")


if __name__ == "__main__":
    unittest.main()
