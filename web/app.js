const FACT_LABELS = {
  core: "内核",
  frequency_mhz: "MHz",
  flash_kb: "Flash KB",
  ram_kb: "RAM KB",
  package: "封装",
  pin_count: "引脚",
  temperature_max_c: "Tmax",
  fdcan: "FDCAN",
  hrtim: "HRTIM",
  motor_timers: "电机定时器",
};

function $(id) {
  return document.getElementById(id);
}

function showMode(mode) {
  document.querySelectorAll(".mode").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.mode === mode);
  });
  $("form-requirements").classList.toggle("is-open", mode === "requirements");
  $("form-competitor").classList.toggle("is-open", mode === "competitor");
  $("form-inspect").classList.toggle("is-open", mode === "inspect");
}

function setBanner(message, isError) {
  const banner = $("banner");
  banner.textContent = message || "";
  banner.classList.toggle("is-on", Boolean(message));
  banner.classList.toggle("error", Boolean(isError));
}

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function collectMust(form) {
  const data = new FormData(form);
  const must = {};
  const minFields = ["frequency_mhz", "flash_kb", "ram_kb", "temperature_max_c", "fdcan"];
  minFields.forEach((name) => {
    const value = numberOrNull(data.get(name));
    if (value !== null) must[name] = { min: value };
  });
  const pins = numberOrNull(data.get("pin_count"));
  if (pins !== null) must.pin_count = { max: pins };
  const packageType = String(data.get("package_type") || "");
  if (packageType) must.package_type = [packageType];
  return must;
}

async function parseResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (response.ok) return payload;
  const detail = payload.detail || payload.error || `请求失败 (${response.status})`;
  throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
}

function factChips(facts) {
  return Object.entries(facts || {})
    .map(([key, value]) => `<span>${FACT_LABELS[key] || key}: ${value}</span>`)
    .join("");
}

function listBlock(title, items) {
  if (!items || items.length === 0) return "";
  return `<div><b>${title}</b><br>${items.map((item) => escapeHtml(item)).join("<br>")}</div>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderCards(payload) {
  const items = payload.recommendations || [];
  if (items.length === 0) {
    $("results").innerHTML = "<p class='meta'>没有满足硬约束的候选。放宽 must 条件后再试。</p>";
    return;
  }
  const cards = items.map((item, index) => {
    const evidence = item.matches || item.comparisons || [];
    return `
      <article class="card">
        <div class="card-head">
          <strong>${index + 1}. ${escapeHtml(item.part_number)}</strong>
          <span>匹配度 ${escapeHtml(item.score)} · ${escapeHtml(item.status || "")}</span>
        </div>
        <div class="facts">${factChips(item.facts)}</div>
        <div class="lists">
          ${listBlock("依据", evidence)}
          ${listBlock("风险 / 缺口", item.risks)}
        </div>
      </article>`;
  });
  const rejected = payload.rejected_by_hard_constraints;
  const extra = rejected === undefined ? "" : `硬约束剔除 ${rejected} 颗。`;
  $("results").innerHTML = `${cards.join("")}<p class="meta">${escapeHtml(payload.disclaimer || "")} ${extra}</p>`;
}

function renderInspect(payload) {
  if (!payload.found) {
    const suggestions = (payload.suggestions || []).map((item) => escapeHtml(item)).join("、");
    $("results").innerHTML = `<p class="meta">未找到 ${escapeHtml(payload.part_number)}。${suggestions ? "相近订货号：" + suggestions : ""}</p>`;
    return;
  }
  const rpn = payload.rpn || {};
  $("results").innerHTML = `
    <article class="card">
      <div class="card-head">
        <strong>${escapeHtml(payload.part_number || "")}</strong>
        <span>${escapeHtml(rpn.marketingStatus || "")}</span>
      </div>
      <div class="facts">${factChips(payload.normalized || {})}</div>
      <p class="meta">${escapeHtml(rpn.description || payload.reference || "")}</p>
    </article>`;
}

async function postJson(url, body) {
  setBanner("正在查询公开 MCU 数据库…", false);
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse(response);
}

$("form-requirements").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  try {
    const payload = await postJson("/api/recommend", {
      must: collectMust(form),
      application: data.get("application") || null,
      unknown_policy: data.get("unknown_policy") || "allow_risk",
      limit: 3,
    });
    setBanner("", false);
    renderCards(payload);
  } catch (error) {
    setBanner(error.message, true);
  }
});

$("form-competitor").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  const specs = {};
  ["frequency_mhz", "flash_kb", "ram_kb", "pin_count", "fdcan"].forEach((name) => {
    const value = numberOrNull(data.get(name));
    if (value !== null) specs[name] = value;
  });
  const packageType = String(data.get("package_type") || "").trim();
  if (packageType) specs.package_type = packageType;
  if (Object.keys(specs).length === 0) {
    setBanner("请至少填写一项已核实的竞品规格。", true);
    return;
  }
  try {
    const payload = await postJson("/api/compare", {
      manufacturer: data.get("manufacturer"),
      part_number: data.get("part_number"),
      source_note: data.get("source_note"),
      specs,
      essential: Object.keys(specs),
      limit: 3,
    });
    setBanner("", false);
    renderCards(payload);
  } catch (error) {
    setBanner(error.message, true);
  }
});

$("form-inspect").addEventListener("submit", async (event) => {
  event.preventDefault();
  const partNumber = new FormData(event.currentTarget).get("part_number");
  try {
    setBanner("正在查询公开 MCU 数据库…", false);
    const response = await fetch(`/api/inspect?part_number=${encodeURIComponent(String(partNumber))}`);
    const payload = await parseResponse(response);
    setBanner("", false);
    renderInspect(payload);
  } catch (error) {
    setBanner(error.message, true);
  }
});

document.querySelectorAll(".mode").forEach((button) => {
  button.addEventListener("click", () => {
    showMode(button.dataset.mode);
    $("results").innerHTML = "";
    setBanner("", false);
  });
});

async function refreshHealth() {
  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    if (response.ok) {
      const count = payload.counts && payload.counts.cpn ? payload.counts.cpn : "";
      $("db-status").textContent = count ? `器件库就绪 · ${count} 个订货号` : "器件库就绪";
      return;
    }
    $("db-status").textContent = payload.error || "器件库未就绪";
  } catch (error) {
    $("db-status").textContent = "无法连接选型服务";
  }
}

refreshHealth();
setInterval(refreshHealth, 8000);
