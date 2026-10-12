from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))

import nl_clone  # noqa: E402

ROW = {
    "vendor": "GigaDevice",
    "part_number": "GD32H759IIT6",
    "url": "https://www.gigadevice.com/product/mcu/mcus-product-selector/gd32h759iit6",
    "fetched_at": "2026-10-12T00:00:00+00:00",
    "status": "ok",
    "cells": {
        "flash_kb": {"value": 2048, "raw": "2048K"},
        "sram_kb": {"value": 1024, "raw": "1024K"},
        "package": {"value": "LQFP", "raw": "LQFP176 (24x24mm)"},
        "pin_count": {"value": 176, "raw": "LQFP176 (24x24mm)"},
    },
}


class DetectTests(unittest.TestCase):
    def test_finds_a_competitor_code_in_a_sentence(self) -> None:
        found = nl_clone.detect("帮我找个能替代 GD32H759IIT6 的型号")
        self.assertEqual(found, {"part_number": "GD32H759IIT6", "vendor": "GigaDevice"})

    def test_our_own_parts_are_not_competitors(self) -> None:
        self.assertIsNone(nl_clone.detect("STM32F103C8T6 够用吗"))

    def test_vendor_comes_from_the_prefix(self) -> None:
        self.assertEqual(nl_clone.detect("APM32F103RCT6")["vendor"], "Geehy")
        self.assertEqual(nl_clone.detect("PY32F030K28U6")["vendor"], "Puya")


class CatalogueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "gigadevice.jsonl"
        path.write_text(json.dumps(ROW, ensure_ascii=False) + "\n", encoding="utf-8")
        self.previous = nl_clone.os.environ.get("ST_MCU_COMPETITOR_DIR")
        nl_clone.os.environ["ST_MCU_COMPETITOR_DIR"] = self.directory.name
        nl_clone.load_catalogue(refresh=True)

    def tearDown(self) -> None:
        if self.previous is None:
            nl_clone.os.environ.pop("ST_MCU_COMPETITOR_DIR", None)
        else:
            nl_clone.os.environ["ST_MCU_COMPETITOR_DIR"] = self.previous
        self.directory.cleanup()
        nl_clone.load_catalogue(refresh=True)

    def test_lookup_is_exact(self) -> None:
        self.assertIsNotNone(nl_clone.lookup("gd32h759iit6"))

    def test_a_sibling_is_not_a_substitute(self) -> None:
        # GD32H759IIK6 is a BGA176 part with different Flash. Serving the T6 row
        # for it is exactly the damage a cross-reference tool must not do.
        self.assertIsNone(nl_clone.lookup("GD32H759IIK6"))

    def test_card_renames_sram_to_the_engine_field(self) -> None:
        card = nl_clone.confirm_card("GD32H759IIT6 的替代")
        self.assertIn("ram_kb", card["known"])
        self.assertNotIn("sram_kb", card["known"])
        self.assertEqual(card["known"]["ram_kb"]["value"], 1024)

    def test_card_still_demands_confirmation(self) -> None:
        card = nl_clone.confirm_card("GD32H759IIT6")
        self.assertTrue(card["needs_confirm"])
        # A product selector states none of the engine's heaviest-weighted
        # fields, so a full harvest never turns into a finished spec set.
        self.assertIn("opamps", card["never_published"])

    def test_card_asks_only_for_what_is_missing(self) -> None:
        card = nl_clone.confirm_card("GD32H759IIT6")
        self.assertIn("frequency_mhz", card["ask"])  # no speed cell in the row
        self.assertNotIn("flash_kb", card["ask"])

    def test_source_note_traces_every_number(self) -> None:
        note = nl_clone.source_note(nl_clone.confirm_card("GD32H759IIT6"))
        self.assertIn("2048K", note)
        self.assertIn("gd32h759iit6", note)

    def test_user_answer_beats_the_harvest(self) -> None:
        card = nl_clone.confirm_card("GD32H759IIT6")
        specs = nl_clone.confirmed_specs(card, {"flash_kb": 512, "frequency_mhz": 600})
        self.assertEqual(specs["flash_kb"], 512)
        self.assertEqual(specs["frequency_mhz"], 600)
        self.assertEqual(specs["ram_kb"], 1024)

    def test_blank_answers_do_not_erase_the_harvest(self) -> None:
        card = nl_clone.confirm_card("GD32H759IIT6")
        specs = nl_clone.confirmed_specs(card, {"flash_kb": ""})
        self.assertEqual(specs["flash_kb"], 2048)


class UnharvestedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        nl_clone.os.environ["ST_MCU_COMPETITOR_DIR"] = self.directory.name
        nl_clone.load_catalogue(refresh=True)

    def tearDown(self) -> None:
        nl_clone.os.environ.pop("ST_MCU_COMPETITOR_DIR", None)
        self.directory.cleanup()
        nl_clone.load_catalogue(refresh=True)

    def test_an_unknown_code_asks_rather_than_guesses(self) -> None:
        card = nl_clone.confirm_card("CS32F103C8T6")
        self.assertEqual(card["vendor"], "Chipsea")
        self.assertEqual(card["known"], {})
        self.assertEqual(card["status"], "not-harvested")
        self.assertEqual(card["ask"], list(nl_clone.ASK_FIELDS))

    def test_source_note_says_so_plainly(self) -> None:
        note = nl_clone.source_note(nl_clone.confirm_card("CS32F103C8T6"))
        self.assertIn("没有这颗料号的抓取记录", note)

    def test_no_code_means_no_card(self) -> None:
        self.assertIsNone(nl_clone.confirm_card("要个 100MHz 带两路 CAN 的"))


if __name__ == "__main__":
    unittest.main()
