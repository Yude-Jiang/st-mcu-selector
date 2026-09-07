import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

describe("ST key visual page", () => {
  it("locks ST palette, Arial, and Chinese TDK", () => {
    const root = process.cwd();
    const html = fs.readFileSync(path.join(root, "web/index.html"), "utf8");
    const css = fs.readFileSync(path.join(root, "web/styles.css"), "utf8");

    assert.match(html, /<title>ST MCU Selector \| STMicroelectronics<\/title>/);
    assert.match(html, /id="root"/);
    assert.match(html, /form-requirements/);
    assert.match(html, />推荐</);
    assert.doesNotMatch(html, /给出短名单/);
    assert.match(css, /#03234b/i);
    assert.match(css, /#ffd200/i);
    assert.match(css, /#3cb4e6/i);
    assert.match(css, /font-family:\s*Arial/);
  });
});
