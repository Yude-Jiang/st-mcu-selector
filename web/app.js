function $(id) {
  return document.getElementById(id);
}

function showMode(mode) {
  document.querySelectorAll(".mode").forEach((button) => {
    const selected = button.dataset.mode === mode;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
    button.tabIndex = selected ? 0 : -1;
  });
  [
    ["requirements", "form-requirements"],
    ["competitor", "form-competitor"],
    ["inspect", "form-inspect"],
  ].forEach(([key, id]) => {
    const panel = $(id);
    const open = key === mode;
    panel.classList.toggle("is-open", open);
    panel.hidden = !open;
  });
}

function clearResults() {
  $("results").innerHTML = "";
  setBanner("", false);
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
  const minFields = ["frequency_mhz", "flash_kb", "ram_kb", "temperature_max_c", "fdcan", "usb", "motor_timers", "hrtim"];
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function factChips(facts) {
  return factEntries(facts)
    .map((item) => `<span>${escapeHtml(item.label)}: ${escapeHtml(item.value)}</span>`)
    .join("");
}

function listBlock(title, items) {
  if (!items || items.length === 0) return "";
  return `<div><b>${title}</b><br>${items.map((item) => escapeHtml(item)).join("<br>")}</div>`;
}

function identityBlock(rows) {
  if (!rows.length) return "";
  const cells = rows
    .map((row) => `<div><dt>${escapeHtml(row.label)}</dt><dd>${escapeHtml(row.value)}</dd></div>`)
    .join("");
  return `<dl class="identity">${cells}</dl>`;
}

function specGroups(groups) {
  return groups
    .map((group) => {
      const chips = group.items
        .map((item) => `<span>${escapeHtml(item.label)}: ${escapeHtml(item.value)}</span>`)
        .join("");
      return `<section class="spec-group"><h3>${escapeHtml(group.title)}</h3><div class="facts">${chips}</div></section>`;
    })
    .join("");
}

function capabilityLists(lists) {
  return lists
    .map((entry) => {
      const items = entry.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      return `<section class="spec-group"><h3>${escapeHtml(entry.title)}</h3><ul class="cap-list">${items}</ul></section>`;
    })
    .join("");
}

function renderCards(payload) {
  const items = payload.recommendations || [];
  if (items.length === 0) {
    $("results").innerHTML = "<p class='meta'>没有满足硬约束的候选。放宽 must 条件后再试。</p>";
    return;
  }
  const mode = payload.mode === "competitor" ? "competitor" : "requirements";
  const cards = items.map((item, index) => {
    const view = shortlistModel(item, index, mode);
    return `
      <article class="card">
        <div class="card-head">
          <strong>${view.rank}. ${escapeHtml(view.partNumber)}</strong>
          <span>匹配度 ${escapeHtml(view.score)}</span>
        </div>
        <p class="status-banner is-${escapeHtml(view.status.kind)}">${escapeHtml(view.status.text)}</p>
        <div class="facts">${view.facts.map((chip) => `<span>${escapeHtml(chip.label)}: ${escapeHtml(chip.value)}</span>`).join("")}</div>
        <div class="lists">
          ${listBlock(view.evidenceTitle, view.evidence)}
          ${listBlock("匹配度说明", view.penalties)}
          ${listBlock("风险 / 缺口", view.risks)}
        </div>
        ${view.otherPackages.length ? `<p class="other-packages"><b>同系列还有这些封装</b><br>${view.otherPackages.map((line) => escapeHtml(line)).join("<br>")}</p>` : ""}
      </article>`;
  });
  const rejected = payload.rejected_by_hard_constraints;
  const extra = rejected === undefined ? "" : `硬约束剔除 ${rejected} 颗。`;
  $("results").innerHTML = `${cards.join("")}<p class="meta">${escapeHtml(payload.disclaimer || "")} ${extra}</p>`;
}

function renderInspect(payload) {
  if (!payload.found) {
    const suggestions = (payload.suggestions || []).map((item) => escapeHtml(item)).join("、");
    $("results").innerHTML = `<p class='meta'>未找到 ${escapeHtml(payload.part_number)}。${suggestions ? "相近订货号：" + suggestions : ""}</p>`;
    return;
  }
  const view = inspectModel(payload);
  $("results").innerHTML = `
    <article class="card inspect-card">
      <div class="card-head">
        <strong>${escapeHtml(view.partNumber)}</strong>
        <a class="st-link" href="${escapeHtml(view.stUrl)}" target="_blank" rel="noopener noreferrer">在 st.com 查看</a>
      </div>
      <p class="status-banner is-${escapeHtml(view.status.kind)}">${escapeHtml(view.status.text)}</p>
      ${view.description ? `<p class="lead-copy">${escapeHtml(view.description)}</p>` : ""}
      ${identityBlock(view.identity)}
      ${specGroups(view.groups)}
      ${capabilityLists(view.lists)}
      <p class="meta">${escapeHtml(view.disclaimer)}</p>
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
  ["frequency_mhz", "flash_kb", "ram_kb", "pin_count", "fdcan", "usb", "motor_timers", "hrtim"].forEach((name) => {
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

const tabs = document.querySelectorAll(".mode");
tabs.forEach((button) => {
  button.addEventListener("click", () => {
    showMode(button.dataset.mode);
    clearResults();
  });
});
document.querySelector(".modes").addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const list = [...tabs];
  const current = list.findIndex((tab) => tab.classList.contains("is-active"));
  let next = current;
  if (event.key === "ArrowRight") next = (current + 1) % list.length;
  if (event.key === "ArrowLeft") next = (current - 1 + list.length) % list.length;
  if (event.key === "Home") next = 0;
  if (event.key === "End") next = list.length - 1;
  event.preventDefault();
  showMode(list[next].dataset.mode);
  list[next].focus();
  clearResults();
});

async function refreshHealth() {
  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    if (response.ok) {
      const count = payload.counts && payload.counts.cpn ? payload.counts.cpn : "";
      $("db-status").textContent = count ? `器件库就绪 · ${count} 个订货号` : "器件库就绪";
    } else {
      $("db-status").textContent = payload.error || "器件库未就绪";
    }
    const notes = $("nl-notes");
    if (notes && payload.llm && notes.dataset.source !== "parse") {
      notes.textContent = payload.llm.configured
        ? "DeepSeek 会把这句话改成硬约束，短名单仍由数据库计算。请核对表单后再查询。"
        : "未配置 DeepSeek 时按关键词抽取。短名单仍由数据库计算。请核对表单后再查询。";
    }
  } catch (error) {
    $("db-status").textContent = "无法连接选型服务";
  }
}

refreshHealth();
setInterval(refreshHealth, 8000);

const footerDate = $("footer-date");
if (footerDate) {
  footerDate.textContent = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date());
}
