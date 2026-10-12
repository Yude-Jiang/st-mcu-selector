from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))

import competitor_spec as spec  # noqa: E402
import nl_must  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def load_harvester():
    """The script is hyphenated, so it is imported by path rather than by name."""
    path = ROOT / "scripts" / "competitor" / "fetch-gigadevice.py"
    loader = importlib.util.spec_from_file_location("fetch_gigadevice", path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


class UnitRuleTests(unittest.TestCase):
    def test_value_suffix_beats_the_column_unit(self) -> None:
        # The label says Bytes, the cell says 3840K. The cell wins.
        self.assertEqual(spec.read_size_kb("3840K", "flash_kb"), 3840)
        self.assertEqual(spec.read_size_kb("2M", "flash_kb"), 2048)

    def test_bare_number_is_rejected(self) -> None:
        # Without a K or M there is no telling KB from bytes, so nothing is kept.
        self.assertIsNone(spec.read_size_kb("3840", "sram_kb"))

    def test_out_of_band_is_rejected(self) -> None:
        self.assertIsNone(spec.read_size_kb("2097152K", "flash_kb"))

    def test_hedged_size_is_rejected(self) -> None:
        # "up to" on a single-part page means we are reading a series maximum.
        self.assertIsNone(spec.read_size_kb("up to 3840K", "flash_kb"))

    def test_frequency_keeps_up_to(self) -> None:
        # A maximum clock is normally written this way, so frequency allows it.
        self.assertEqual(spec.read_frequency_mhz("up to 600 MHz"), 600)


class PinCountTests(unittest.TestCase):
    def test_pins_come_from_the_package_token(self) -> None:
        self.assertEqual(spec.read_package("LQFP176 (24x24mm)"), ("LQFP", 176))
        self.assertEqual(spec.read_package("BGA176"), ("BGA", 176))

    def test_loose_number_is_not_a_pin_count(self) -> None:
        # "up to 121" is a GPIO count; no package token, so no pins.
        self.assertEqual(spec.read_package("up to 121"), ("", None))

    def test_gpio_cell_cannot_reach_pin_count(self) -> None:
        row = spec.build_row("GD32H759IIT6", {"gpio": "up to 121"}, "u", "t")
        self.assertNotIn("pin_count", row["cells"])


class InterfaceCountTests(unittest.TestCase):
    def test_a_named_interface_without_a_count_is_blank(self) -> None:
        self.assertIsNone(spec.read_interface_count("I2C"))
        self.assertIsNone(spec.read_interface_count("Yes"))

    def test_a_count_is_kept(self) -> None:
        self.assertEqual(spec.read_interface_count("4"), 4)

    def test_harvest_differs_from_sentence_parsing(self) -> None:
        # nl_must reads a bare mention as 1 because a user asking for I2C wants
        # at least one. A spec table printing a bare "I2C" states no count, and
        # harvesting it as 1 would write an invented number into the catalogue.
        self.assertEqual(nl_must.i2c_min("要带I2C"), 1)
        self.assertIsNone(spec.read_interface_count("I2C"))


class TitleTests(unittest.TestCase):
    def test_exact_part_in_title(self) -> None:
        self.assertTrue(spec.title_matches("GD32H759IIT6 | GigaDevice", "GD32H759IIT6"))

    def test_sibling_title_does_not_match(self) -> None:
        self.assertFalse(spec.title_matches("GD32H759IIK6 | GigaDevice", "GD32H759IIT6"))

    def test_generic_title_does_not_match(self) -> None:
        # An empty client-rendered shell looks like this; it must not read as a
        # part that happens to have no specs.
        self.assertFalse(spec.title_matches("MCUs Product Selector", "GD32H759IIT6"))


class HarvestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harvester = load_harvester()

    def harvest(self, code: str, fixture: str) -> dict:
        html = (FIXTURES / fixture).read_text(encoding="utf-8")
        return self.harvester.harvest_html(code, html, "https://www.gigadevice.com/x")

    def test_definition_list_page(self) -> None:
        row = self.harvest("GD32H759IIT6", "gigadevice-gd32h759iit6.html")
        cells = row["cells"]
        self.assertEqual(cells["core"]["value"], "Cortex-M7")
        self.assertEqual(cells["frequency_mhz"]["value"], 600)
        self.assertEqual(cells["flash_kb"]["value"], 2048)
        self.assertEqual(cells["sram_kb"]["value"], 1024)
        self.assertEqual(cells["package"]["value"], "LQFP")
        self.assertEqual(cells["pin_count"]["value"], 176)
        self.assertEqual(cells["i2c"]["value"], 4)

    def test_siblings_do_not_share_specs(self) -> None:
        # Same series, different ordering code, different Flash and package.
        table = self.harvest("GD32H759IIK6", "gigadevice-gd32h759iik6.html")["cells"]
        self.assertEqual(table["flash_kb"]["value"], 3840)
        self.assertEqual(table["package"]["value"], "BGA")
        self.assertEqual(table["pin_count"]["value"], 176)
        self.assertNotIn("sram_kb", table)  # bare 3840, no suffix to read
        self.assertNotIn("i2c", table)  # named without a count

    def test_every_kept_cell_carries_its_source_text(self) -> None:
        row = self.harvest("GD32H759IIT6", "gigadevice-gd32h759iit6.html")
        for field, cell in row["cells"].items():
            self.assertTrue(cell["raw"], f"{field} kept a value with no source text")
        self.assertTrue(row["url"])
        self.assertTrue(row["fetched_at"])

    def test_title_mismatch_yields_no_cells(self) -> None:
        row = self.harvest("GD32H759IIT6", "gigadevice-wrong-title.html")
        self.assertEqual(row["status"], "title-mismatch")
        self.assertEqual(row["cells"], {})

    def test_series_name_is_never_fetched(self) -> None:
        # GD32H779 is a series and 404s; only complete ordering codes are tried.
        self.assertFalse(self.harvester.looks_complete("GD32H779"))
        self.assertTrue(self.harvester.looks_complete("GD32H759IIT6"))

    def test_conflicting_labels_are_dropped(self) -> None:
        # A listing page repeats a label with different values per row, and there
        # is no way to tell which row is the code we asked for.
        html = (
            "<html><head><title>GD32H759IIT6</title></head><body><table><tbody>"
            "<tr><th>Flash (Bytes)</th><td>2048K</td></tr>"
            "<tr><th>Flash (Bytes)</th><td>3840K</td></tr>"
            "</tbody></table></body></html>"
        )
        row = self.harvester.harvest_html("GD32H759IIT6", html, "u")
        self.assertNotIn("flash_kb", row["cells"])
        self.assertIn("flash (bytes)", row["ambiguous_labels"])

    def test_url_is_the_lowercased_code(self) -> None:
        self.assertEqual(
            self.harvester.part_url("GD32H759IIT6"),
            "https://www.gigadevice.com/product/mcu/mcus-product-selector/gd32h759iit6",
        )


if __name__ == "__main__":
    unittest.main()
