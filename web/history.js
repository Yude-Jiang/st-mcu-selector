const HISTORY_KEY = "st-mcu-history";
const HISTORY_LIMIT = 20;
let activeHistoryId = "";

function readHistory() {
  try {
    const raw = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch (error) {
    return [];
  }
}

function writeHistory(items) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, HISTORY_LIMIT)));
  } catch (error) {
    /* private mode or quota */
  }
}

function clearConstraintFields(form) {
  [
    "frequency_mhz", "flash_kb", "ram_kb", "temperature_max_c",
    "fdcan", "usb", "i2c", "motor_timers", "hrtim", "pin_count",
  ].forEach((name) => {
    if (form.elements[name]) form.elements[name].value = "";
  });
  if (form.elements.package_type) form.elements.package_type.value = "";
  if (form.elements.compact_package) form.elements.compact_package.checked = false;
  if (form.elements.application) form.elements.application.value = "";
}

function recordHistory(form) {
  const text = (
    ($("nl-text") && $("nl-text").value.trim())
    || ($("followup-text") && $("followup-text").value.trim())
    || ""
  );
  const summary = typeof constraintSummary === "function" ? constraintSummary(form) : "";
  if (!text && !summary) return;
  const item = {
    id: activeHistoryId || String(Date.now()),
    at: new Date().toISOString(),
    text,
    summary,
    must: collectMust(form),
    application: form.elements.application.value || "",
    unknown_policy: form.elements.unknown_policy.value || "allow_risk",
    compact_package: Boolean(form.elements.compact_package && form.elements.compact_package.checked),
  };
  const rest = readHistory().filter((row) => row.id !== item.id);
  writeHistory([item].concat(rest));
  activeHistoryId = "";
  renderHistory();
}

function loadHistory(item) {
  activeHistoryId = item.id;
  const form = $("form-requirements");
  if ($("nl-text")) $("nl-text").value = item.text || "";
  if (form) clearConstraintFields(form);
  if (typeof applyRecommendDraft === "function") {
    applyRecommendDraft({
      must: item.must || {},
      application: item.application || "",
      unknown_policy: item.unknown_policy || "allow_risk",
      compact_package: Boolean(item.compact_package),
    });
  }
  const panel = $("must-panel");
  if (panel) panel.open = true;
  const historyPanel = $("history-panel");
  if (historyPanel) historyPanel.open = true;
}

function renderHistory() {
  const list = $("history-list");
  if (!list) return;
  const items = readHistory();
  if (!items.length) {
    list.innerHTML = `<p class="history-empty">${escapeHtml(t("history.empty"))}</p>`;
    return;
  }
  list.innerHTML = items.map((item) => {
    const label = item.text || item.summary || t("history.item");
    return `<button type="button" class="history-item" data-history-id="${escapeHtml(item.id)}"><span class="history-time">${escapeHtml(formatHistoryTime(item.at))}</span><span class="history-text">${escapeHtml(label)}</span></button>`;
  }).join("");
}

function formatHistoryTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const locale = typeof getLang === "function" && getLang() === "en" ? "en-CA" : "zh-CN";
  return new Intl.DateTimeFormat(locale, {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function bindHistory() {
  const list = $("history-list");
  if (!list) return;
  list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-history-id]");
    if (!button) return;
    const item = readHistory().find((row) => row.id === button.getAttribute("data-history-id"));
    if (item) loadHistory(item);
  });
  renderHistory();
}

bindHistory();
if (typeof onLangChange === "function") onLangChange(renderHistory);
