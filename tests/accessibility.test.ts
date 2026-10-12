import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const SHEETS = fs
  .readdirSync(path.join(ROOT, "web"))
  .filter((name) => name.endsWith(".css"))
  .sort();
const CSS = SHEETS.map((name) =>
  fs.readFileSync(path.join(ROOT, "web", name), "utf8"),
).join("\n");

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

function rules(): Array<{ selector: string; body: string }> {
  return [...CSS.matchAll(/([^{}]+)\{([^}]*)\}/g)].map(([, selector, body]) => ({
    selector: selector.trim().split("\n").pop()!.trim(),
    body,
  }));
}

describe("colour contrast", () => {
  // Computed from the stylesheets, so this covers the whole palette rather than
  // whichever single rule happened to be wrong when it was written.
  it("every palette pairing meets WCAG AA", () => {
    const colours = palette();
    const failures: string[] = [];

    for (const { selector, body } of rules()) {
      const bg = body.match(/background(?:-color)?:\s*var\(--st-([a-z0-9-]+)\)/);
      const fg = body.match(/(?<!-)color:\s*var\(--st-([a-z0-9-]+)\)/);
      if (!bg || !fg || !colours[bg[1]] || !colours[fg[1]]) continue;

      const sizeMatch = body.match(/font-size:\s*(\d+)px/);
      const weightMatch = body.match(/font-weight:\s*(\d+)/);
      const size = sizeMatch ? Number(sizeMatch[1]) : 14;
      const weight = weightMatch ? Number(weightMatch[1]) : 400;
      const required = size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5;
      const ratio = contrast(colours[fg[1]], colours[bg[1]]);

      if (ratio < required) {
        failures.push(
          `${selector}: --st-${fg[1]} on --st-${bg[1]} = ${ratio.toFixed(2)}:1, needs ${required}:1`,
        );
      }
    }

    assert.deepEqual(failures, [], `contrast failures:\n${failures.join("\n")}`);
  });
});

describe("touch targets", () => {
  // The mini program renders this page in a web-view, so every control is thumb
  // input on a phone. 44px is the floor; below 16px iOS zooms the page on focus.
  const INTERACTIVE = /button|summary|\.lang(?![a-z-])|input|select|textarea/;

  it("no interactive rule sits under 44px", () => {
    const failures = rules()
      .map(({ selector, body }) => {
        const height = body.match(/min-height:\s*(\d+)px/);
        if (!height || !INTERACTIVE.test(selector)) return null;
        const value = Number(height[1]);
        return value > 0 && value < 44 ? `${selector}: ${value}px` : null;
      })
      .filter(Boolean);

    assert.deepEqual(failures, [], `touch targets under 44px:\n${failures.join("\n")}`);
  });

  it("controls that only have padding still declare a floor", () => {
    // A rule with no min-height at all passes the check above while still
    // rendering at 42px, which is how .history-panel summary slipped through.
    // Enumerate the selectors rather than listing them, so new ones are covered.
    const sized = rules().filter(({ selector }) =>
      /\bsummary\b/.test(selector) || /\.lang(?![a-z-])\s*$/.test(selector),
    );
    assert.ok(sized.length >= 2, "expected the disclosure and language controls");

    const failures = sized
      .filter(({ selector }) => !selector.includes("::"))
      .map(({ selector, body }) => {
        const height = body.match(/min-height:\s*(\d+)px/);
        if (!height) return `${selector}: no min-height, padding alone is under 44px`;
        return Number(height[1]) >= 44 ? null : `${selector}: ${height[1]}px`;
      })
      .filter(Boolean);

    assert.deepEqual(failures, [], `padding-sized controls:\n${failures.join("\n")}`);
  });

  it("form controls use at least 16px so iOS does not zoom on focus", () => {
    const rule = CSS.match(/\.field input,\s*\.field select,\s*\.field textarea\s*\{([^}]*)\}/);
    assert.ok(rule, ".field control rule is missing");
    const size = rule![1].match(/font-size:\s*(\d+)px/);
    assert.ok(size, "form controls need an explicit font-size");
    assert.ok(Number(size![1]) >= 16, `form controls are ${size![1]}px`);
  });
});

describe("mini program web-view", () => {
  const PAGE = path.join(ROOT, "miniprogram/pages/index/index.js");
  const CONFIG = path.join(ROOT, "miniprogram/config.js");

  it("refuses http before rendering, because web-view cannot load it", () => {
    const page = fs.readFileSync(PAGE, "utf8");
    assert.match(page, /\^https:\\\/\\\//, "page must check the scheme");
    assert.match(page, /failed:\s*true/, "a rejected URL needs a visible state");
  });

  it("has a load-failure path instead of a blank screen", () => {
    const page = fs.readFileSync(PAGE, "utf8");
    const wxml = fs.readFileSync(path.join(ROOT, "miniprogram/pages/index/index.wxml"), "utf8");
    assert.match(wxml, /binderror=/, "web-view needs binderror");
    assert.match(page, /onWebViewError/, "binderror needs a handler");
    // web-view fills its page, so the fallback replaces it rather than overlaying.
    assert.match(wxml, /wx:else/, "the fallback must replace the web-view");
  });

  it("never points the web-view at http", () => {
    const config = fs.readFileSync(CONFIG, "utf8");
    const hosts = config.match(/const HOSTS\s*=\s*\{([\s\S]*?)\n\};/);
    assert.ok(hosts, "HOSTS block is missing");

    // Read the quoted values rather than stripping comments: a `//` stripper also
    // eats the slashes inside "https://", which made this assertion unfailable.
    const urls = [...hosts![1].matchAll(/"([^"]+)"/g)].map(([, value]) => value);
    assert.ok(urls.length > 0, "no host values found");
    const insecure = urls.filter((url) => url.startsWith("http://"));
    assert.deepEqual(
      insecure,
      [],
      `web-view cannot load http; these render a blank page: ${insecure.join(", ")}`,
    );
  });

  it("marks the embed so the page skips the gate", () => {
    const config = fs.readFileSync(CONFIG, "utf8");
    const mp = fs.readFileSync(path.join(ROOT, "web/mp.js"), "utf8");
    // Both sides agree on ?mp=1; renaming one alone would restore the gate.
    assert.match(config, /\?mp=1/);
    assert.match(mp, /get\("mp"\)\s*===\s*"1"/);
  });
});
