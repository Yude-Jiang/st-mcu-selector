import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const ROOT = process.cwd();
const PAGE = path.join(ROOT, "miniprogram/pages/web/index.js");
const GATE = path.join(ROOT, "web/gate.js");
const CONFIG = path.join(ROOT, "miniprogram/config.js");

type PageOptions = {
  data: Record<string, unknown>;
  load: () => void;
};

/** Run the web-view page module with a stub config and return its Page() options. */
function loadPage(webBase: string): PageOptions {
  let captured: PageOptions | undefined;
  const sandbox = {
    require: (id: string) => {
      if (id === "../../config") return { webBase, env: "develop" };
      throw new Error(`unexpected require: ${id}`);
    },
    Page: (options: PageOptions) => {
      captured = options;
    },
    wx: { setClipboardData: () => {}, showToast: () => {} },
    module: { exports: {} },
  };
  vm.runInNewContext(fs.readFileSync(PAGE, "utf8"), sandbox, { filename: PAGE });
  if (!captured) throw new Error("Page() was never called");
  return captured;
}

/** Drive the page's load() against a minimal setData harness. */
function runLoad(webBase: string): Record<string, unknown> {
  const options = loadPage(webBase);
  const data: Record<string, unknown> = { ...options.data };
  const self = {
    data,
    setData(patch: Record<string, unknown>) {
      Object.assign(data, patch);
    },
  };
  options.load.call(self);
  return data;
}

describe("mini program web-view shell", () => {
  it("marks the embed so the page knows which shell loaded it", () => {
    const data = runLoad("https://mp.microelectronics.com");
    assert.equal(data.failed, false);
    assert.equal(data.url, "https://mp.microelectronics.com?embed=miniprogram");
  });

  it("keeps an existing query string instead of clobbering it", () => {
    const data = runLoad("https://mp.microelectronics.com/?lang=en");
    assert.equal(data.url, "https://mp.microelectronics.com/?lang=en&embed=miniprogram");
  });

  it("drops a trailing slash so the query separator stays correct", () => {
    const data = runLoad("https://example.run.app/");
    assert.equal(data.url, "https://example.run.app?embed=miniprogram");
  });

  it("refuses http before rendering, since web-view only accepts https", () => {
    const data = runLoad("http://127.0.0.1:8080");
    assert.equal(data.failed, true);
    assert.match(String(data.hint), /https/);
  });
});

describe("gate bypass contract", () => {
  // The shell and the page agree on this string across two languages and two
  // directories; a rename on one side alone would silently restore the gate.
  it("uses the same embed marker on both sides", () => {
    const page = fs.readFileSync(PAGE, "utf8");
    const gate = fs.readFileSync(GATE, "utf8");

    assert.match(page, /embed=miniprogram/);
    assert.match(gate, /EMBED_PARAM\s*=\s*"embed"/);
    assert.match(gate, /EMBED_MINIPROGRAM\s*=\s*"miniprogram"/);
  });

  it("suppresses the gate before the blocking scripts load", () => {
    // gate.js sits behind three network-fetched blocking scripts, so without a
    // parse-time rule the gate paints for that window on a phone.
    const html = fs.readFileSync(path.join(ROOT, "web/index.html"), "utf8");
    const css = fs.readFileSync(path.join(ROOT, "web/styles.css"), "utf8");

    const head = html.slice(0, html.indexOf("</head>"));
    assert.match(head, /embed.*miniprogram/s, "head needs the pre-parse embed check");
    assert.match(head, /data-embed/, "head script must stamp the root element");
    assert.match(css, /:root\[data-embed="miniprogram"\] #gate\s*\{\s*display: none/);
    assert.match(css, /:root\[data-embed="miniprogram"\] #root\[hidden\]\s*\{\s*display: block/);
  });

  it("still gates a plain browser visit", () => {
    const gate = fs.readFileSync(GATE, "utf8");
    // startGate must return early only for the embed case; the email path stays.
    assert.match(gate, /if \(isEmbedded\(\)\) \{[\s\S]*?showMainApp\(\);[\s\S]*?return;/);
    assert.match(gate, /isStEmail\(readGateEmail\(\)\)/);
  });
});

describe("mini program config", () => {
  it("keeps apiBase and webBase separate", () => {
    // They map to two unrelated WeChat settings (request 合法域名 vs 业务域名);
    // collapsing them back into one value would misconfigure one of the two.
    const config = fs.readFileSync(CONFIG, "utf8");
    assert.match(config, /apiBase:/);
    assert.match(config, /webBase:/);
  });

  it("points production at the filed domain for both", () => {
    const sandbox = { module: { exports: {} as Record<string, unknown> } };
    vm.runInNewContext(fs.readFileSync(CONFIG, "utf8"), sandbox, { filename: CONFIG });
    const exported = sandbox.module.exports;
    assert.ok(typeof exported.apiBase === "string" && exported.apiBase.length > 0);
    assert.ok(typeof exported.webBase === "string" && exported.webBase.length > 0);
    // web-view cannot load http, so whatever env is selected, webBase must be https
    // unless it is deliberately the local API host.
    assert.match(String(exported.webBase), /^https:\/\//);
  });
});
