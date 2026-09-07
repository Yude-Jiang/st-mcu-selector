function $(id) {
  return document.getElementById(id);
}

let lastHealth = null;
let lastHealthOk = false;
let lastHealthError = false;

function showMode(mode) {
  document.querySelectorAll(".mode").forEach((button) => {
    const selected = button.dataset.mode === mode;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
    button.tabIndex = selected ? 0 : -1;
  });
  [
    ["requirements", "form-requirements"],
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
  const detail = payload.detail || payload.error || t("requestFailed", { status: response.status });
  throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
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

function compareLeadHtml(payload) {
  const competitor = payload && payload.compare;
  if (!competitor || payload.mode !== "competitor") return "";
  const name = [competitor.manufacturer, competitor.part_number].filter(Boolean).join(" ");
  const specs = competitor.specs || {};
  const bits = [];
  if (specs.frequency_mhz != null) bits.push(t("compare.freq", { value: specs.frequency_mhz }));
  if (specs.flash_kb != null) bits.push(t("compare.flash", { value: specs.flash_kb }));
  if (specs.ram_kb != null) bits.push(t("compare.ram", { value: specs.ram_kb }));
  if (specs.pin_count != null) bits.push(t("compare.pins", { value: specs.pin_count }));
  if (specs.package_type) bits.push(String(specs.package_type));
  const specLine = bits.length ? t("compare.specs", { bits: bits.join(getLang() === "en" ? ", " : "，") }) : "";
  return `<p class="compare-lead">${escapeHtml(t("compare.lead", { name, specs: specLine }))}</p>`;
}

function paintCards(payload) {
  const items = payload.recommendations || [];
  const mode = payload.mode === "competitor" ? "competitor" : "requirements";
  const heading = mode === "competitor" ? t("heading.shortlistCompare") : t("heading.shortlist");
  const lead = compareLeadHtml(payload);
  const table = typeof compareTableHtml === "function" ? compareTableHtml(payload) : "";
  if (items.length === 0) {
    const empty = mode === "competitor" ? t("empty.competitor") : t("empty.requirements");
    $("results").innerHTML = `<h2 class="results-title">${heading}</h2>${lead}${table}<p class="meta">${empty}</p>`;
    return;
  }
  const cards = items.map((item, index) => {
    const view = shortlistModel(item, index, mode);
    const scoreText = mode === "competitor"
      ? t("score.closeness", { score: view.score })
      : t("score", { score: view.score });
    return `
      <article class="card">
        <div class="card-head">
          <strong>${view.rank}. ${escapeHtml(view.partNumber)}</strong>
          <span>${escapeHtml(scoreText)}</span>
          <a class="st-link" href="${escapeHtml(view.stUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("stProduct"))}</a>
        </div>
        <p class="status-banner is-${escapeHtml(view.status.kind)}">${escapeHtml(view.status.text)}</p>
        ${view.decisionNote ? `<p class="decision">${escapeHtml(view.decisionNote)}</p>` : ""}
        <div class="facts">${view.facts.map((chip) => `<span>${escapeHtml(chip.label)}: ${escapeHtml(chip.value)}</span>`).join("")}</div>
        <div class="lists">${listBlock(view.evidenceTitle, view.matchLines)}</div>
        ${view.otherPackages.length ? `<p class="other-packages"><b>${escapeHtml(t("otherPackages"))}</b><br>${view.otherPackages.map((line) => escapeHtml(line)).join("<br>")}</p>` : ""}
      </article>`;
  });
  const rejected = payload.rejected_by_hard_constraints;
  const extra = rejected === undefined ? "" : t("rejected", { count: rejected });
  $("results").innerHTML = `<h2 class="results-title">${heading}</h2>${lead}${table}${cards.join("")}<p class="meta">${escapeHtml(payload.disclaimer || "")} ${extra}</p>`;
}

function paintInspect(payload) {
  if (!payload.found) {
    const suggestions = (payload.suggestions || []).map((item) => escapeHtml(item)).join(getLang() === "en" ? ", " : "、");
    const near = suggestions ? t("nearParts", { list: suggestions }) : "";
    $("results").innerHTML = `<p class='meta'>${escapeHtml(t("notFound", { part: payload.part_number }))}${near}</p>`;
    return;
  }
  const view = inspectModel(payload);
  $("results").innerHTML = `
    <article class="card inspect-card">
      <div class="card-head">
        <strong>${escapeHtml(view.partNumber)}</strong>
        <a class="st-link" href="${escapeHtml(view.stUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("stCom"))}</a>
      </div>
      <p class="status-banner is-${escapeHtml(view.status.kind)}">${escapeHtml(view.status.text)}</p>
      ${view.description ? `<p class="lead-copy">${escapeHtml(view.description)}</p>` : ""}
      ${identityBlock(view.identity)}
      ${specGroups(view.groups)}
      ${capabilityLists(view.lists)}
      <p class="meta">${escapeHtml(view.disclaimer)}</p>
    </article>`;
}

function renderCards(payload) {
  paintCards(payload);
}

function renderInspect(payload) {
  paintInspect(payload);
}

async function postJson(url, body) {
  setBanner(t("querying"), false);
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
  const text = ($("nl-text") && $("nl-text").value.trim()) || "";
  try {
    if (text.length >= 4 || (typeof attachedDatasheetFile === "function" && attachedDatasheetFile())) {
      const prompt = text.length >= 2 ? text : t("uploadPrompt");
      if (typeof askEngine === "function") {
        await askEngine(prompt, { seed: true });
        return;
      }
    }
    const data = new FormData(form);
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

$("form-inspect").addEventListener("submit", async (event) => {
  event.preventDefault();
  const partNumber = new FormData(event.currentTarget).get("part_number");
  try {
    setBanner(t("querying"), false);
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
});

function applyHealthCopy() {
  const pill = $("db-status");
  const notes = $("nl-notes");
  if (!pill) return;
  if (!lastHealth) {
    pill.textContent = lastHealthError ? t("db.offline") : t("db.loading");
    if (notes && notes.dataset.source !== "parse") notes.textContent = t("nl.notes");
    return;
  }
  if (lastHealthOk) {
    const count = lastHealth.counts && lastHealth.counts.cpn;
    pill.textContent = count ? t("db.readyCount", { count }) : t("db.ready");
  } else {
    pill.textContent = lastHealth.error || t("db.notReady");
  }
  if (notes && notes.dataset.source !== "parse") {
    notes.textContent = lastHealth.llm && lastHealth.llm.configured ? t("nl.notesLlm") : t("nl.notesRules");
  }
}

async function refreshHealth() {
  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    lastHealth = payload;
    lastHealthOk = response.ok;
    lastHealthError = false;
    applyHealthCopy();
  } catch (error) {
    lastHealth = null;
    lastHealthOk = false;
    lastHealthError = true;
    applyHealthCopy();
  }
}

refreshHealth();
setInterval(refreshHealth, 8000);

const footerDate = $("footer-date");
if (footerDate) {
  footerDate.textContent = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date());
}
