import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const SHEETS = ["web/styles.css", "web/forms.css", "web/chat.css"];
const CSS = SHEETS.map((name) => fs.readFileSync(path.join(ROOT, name), "utf8")).join("\n");

/** WCAG relative luminance. */
function luminance(hex: string): number {
  const value = hex.replace("#", "");
  const channels = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function palette(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [, name, hex] of CSS.matchAll(/--st-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)) {
    out[name] = hex;
  }
  return out;
}

type Pair = { selector: string; fg: string; bg: string; size: number; weight: number };

/** Every rule that sets a palette background and a palette foreground together. */
function colourPairs(): Pair[] {
  const pairs: Pair[] = [];
  for (const [, selector, body] of CSS.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    const bg = body.match(/background(?:-color)?:\s*var\(--st-([a-z0-9-]+)\)/);
    const fg = body.match(/(?<!-)color:\s*var\(--st-([a-z0-9-]+)\)/);
    if (!bg || !fg) continue;
    const size = body.match(/font-size:\s*(\d+)px/);
    const weight = body.match(/font-weight:\s*(\d+)/);
    pairs.push({
      selector: selector.trim().split("\n").pop()!.trim(),
      fg: fg[1],
      bg: bg[1],
      size: size ? Number(size[1]) : 14,
      weight: weight ? Number(weight[1]) : 400,
    });
  }
  return pairs;
}

describe("colour contrast", () => {
  it("every palette pairing meets WCAG AA", () => {
    const colours = palette();
    const failures: string[] = [];

    for (const pair of colourPairs()) {
      const fg = colours[pair.fg];
      const bg = colours[pair.bg];
      if (!fg || !bg) continue;
      const large = pair.size >= 24 || (pair.size >= 18.66 && pair.weight >= 700);
      const required = large ? 3 : 4.5;
      const ratio = contrast(fg, bg);
      if (ratio < required) {
        failures.push(
          `${pair.selector}: --st-${pair.fg} on --st-${pair.bg} = ${ratio.toFixed(2)}:1, needs ${required}:1`,
        );
      }
    }

    assert.deepEqual(failures, [], `contrast failures:\n${failures.join("\n")}`);
  });

  it("keeps the disclaimer bar readable", () => {
    // White on ST Light Blue is 2.37:1. This bar carries the "shortlist, not a design
    // sign-off" line, so it is the one that must not regress.
    const colours = palette();
    const rule = CSS.match(/\.message-bar\s*\{([^}]*)\}/);
    assert.ok(rule, ".message-bar rule is missing");
    const fg = rule![1].match(/(?<!-)color:\s*var\(--st-([a-z0-9-]+)\)/);
    assert.ok(fg, ".message-bar must set a palette colour");
    assert.ok(
      contrast(colours[fg![1]], colours["cyan"]) >= 4.5,
      `.message-bar text on cyan must clear 4.5:1`,
    );
  });
});

describe("touch targets", () => {
  // The mini program embeds this page in a web-view, so every control is finger-sized
  // input only. 44px is the floor; 16px keeps iOS from zooming on focus.
  // Each entry is a complete rule matcher capturing the declaration block. The
  // language switch needs the lookahead so it does not match the `.langs` container.
  const RULES: Array<[RegExp, string]> = [
    [/\.field input,\s*\.field select,\s*\.field textarea\s*\{([^}]*)\}/, "form controls"],
    [/\.must-panel summary\s*\{([^}]*)\}/, "hard-constraints disclosure"],
    [/\.lang(?![a-z-])\s*\{([^}]*)\}/, "language switch"],
    [/\.followup > button\s*\{([^}]*)\}/, "follow-up send"],
  ];

  for (const [pattern, label] of RULES) {
    it(`${label} is at least 44px tall`, () => {
      const rule = CSS.match(pattern);
      assert.ok(rule, `no rule matched ${label}`);
      const height = rule![1].match(/min-height:\s*(\d+)px/);
      assert.ok(height, `${label} needs an explicit min-height`);
      assert.ok(
        Number(height![1]) >= 44,
        `${label} is ${height![1]}px, below the 44px touch floor`,
      );
    });
  }

  it("form controls use at least 16px so iOS does not zoom on focus", () => {
    const rule = CSS.match(/\.field input,\s*\.field select,\s*\.field textarea\s*\{([^}]*)\}/);
    assert.ok(rule, ".field control rule is missing");
    const size = rule![1].match(/font-size:\s*(\d+)px/);
    assert.ok(size, "form controls need an explicit font-size");
    assert.ok(Number(size![1]) >= 16, `form controls are ${size![1]}px, iOS will zoom below 16px`);
  });
});
