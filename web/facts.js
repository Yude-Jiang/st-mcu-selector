const IDENTITY_KEYS = ["core", "frequency_mhz", "flash_kb", "ram_kb", "package", "pin_count"];
const SHORTLIST_KEYS = [
  "core", "frequency_mhz", "flash_kb", "ram_kb", "package", "pin_count",
  "temperature_max_c", "fdcan", "usb", "motor_timers", "hrtim",
];
const SPEC_GROUP_KEYS = [
  { titleKey: "group.operating", keys: ["temperature_min_c", "temperature_max_c", "voltage_min_v", "voltage_max_v"] },
  { titleKey: "group.comm", keys: ["fdcan", "can", "usb", "usb_types", "ethernet", "ethernet_speed_mbps"] },
  { titleKey: "group.analog", keys: ["adc_channels", "adc_units", "opamps", "comparators", "dac_channels", "motor_timers", "hrtim", "timers", "timers_16bit", "timers_32bit"] },
];
const LIST_KEY_DEFS = [
  { key: "security", titleKey: "list.security" },
  { key: "other_timer_functions", titleKey: "list.timers" },
];

function factLabel(key) {
  const label = t(`fact.${key}`);
  return label === `fact.${key}` ? key : label;
}

function hasFactValue(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") {
    const text = value.trim().toLowerCase();
    return text !== "" && text !== "null" && text !== "none";
  }
  return true;
}

function formatFactValue(key, value) {
  if (!hasFactValue(value)) return "";
  if (key === "frequency_mhz") return `${value} MHz`;
  if (key === "flash_kb" || key === "ram_kb") return `${value} KB`;
  if (key === "temperature_min_c" || key === "temperature_max_c") return `${value} °C`;
  if (key === "voltage_min_v" || key === "voltage_max_v") return `${value} V`;
  if (key === "ethernet_speed_mbps") return `${value} Mbps`;
  return String(value);
}

function factEntries(facts, keys) {
  const source = facts || {};
  const selected = keys || Object.keys(source);
  return selected
    .filter((key) => hasFactValue(source[key]))
    .map((key) => ({
      key,
      label: factLabel(key),
      value: formatFactValue(key, source[key]),
    }));
}

function splitFactList(value) {
  return String(value)
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean);
}

function lifecycleStatus(raw) {
  const status = String(raw || "").trim();
  const lower = status.toLowerCase();
  if (!status) return { kind: "unknown", text: t("status.unknown") };
  if (lower.includes("coming soon")) {
    return { kind: "soon", text: t("status.soon") };
  }
  if (lower.includes("obsolete")) return { kind: "obsolete", text: t("status.obsolete") };
  if (lower.includes("nrnd") || lower.includes("not recommended")) {
    return { kind: "nrnd", text: t("status.nrnd") };
  }
  if (lower.includes("active")) return { kind: "active", text: t("status.active") };
  return { kind: "other", text: t("status.other", { status }) };
}

function stComSearchUrl(partNumber) {
  const query = encodeURIComponent(String(partNumber || "").trim());
  return `https://www.st.com/content/st_com/en/search.html#q=${query}&t=products`;
}

function stProductUrl(partNumber, rpn) {
  const commercial = String(rpn || "").trim().toLowerCase();
  if (commercial) {
    return `https://www.st.com/en/microcontrollers-microprocessors/${encodeURIComponent(commercial)}.html`;
  }
  return stComSearchUrl(partNumber);
}

function matchLines(item, mode) {
  const lines = [];
  const description = String(item.description || "").trim();
  if (description) lines.push(t("match.positioning", { text: description }));
  if (item.score != null && item.score !== "") {
    lines.push(t("match.score", { score: item.score }));
  }
  const prefixKey = mode === "competitor" ? "match.compare" : "match.meet";
  (item.matches || item.comparisons || []).forEach((row) => {
    if (row) lines.push(t(prefixKey, { row }));
  });
  (item.penalties || []).forEach((row) => {
    if (row) lines.push(t("match.penalty", { row }));
  });
  (item.risks || []).forEach((row) => {
    if (row) lines.push(t("match.risk", { row }));
  });
  return lines;
}

function inspectModel(payload) {
  const facts = payload.normalized || {};
  const rpn = payload.rpn || {};
  const partNumber = payload.part_number || payload.queried || payload.reference || "";
  return {
    partNumber,
    stUrl: stProductUrl(partNumber, rpn.rpn),
    status: lifecycleStatus(rpn.marketingStatus),
    description: rpn.description || payload.reference || "",
    tableRows: factEntries(facts),
    orderables: payload.orderables || [],
    sampleNote: payload.sample_orderable
      ? t("inspect.fromOrderable", { part: payload.sample_orderable })
      : "",
    disclaimer: t("inspect.disclaimer"),
  };
}

function inspectSpecTable(rows) {
  if (!rows.length) return "";
  const body = rows
    .map((row) => `<tr><th>${escapeHtml(row.label)}</th><td>${escapeHtml(row.value)}</td></tr>`)
    .join("");
  return `<div class="inspect-table-wrap">
    <h3 class="inspect-table-title">${escapeHtml(t("inspect.table"))}</h3>
    <table class="inspect-table">
      <thead><tr><th>${escapeHtml(t("table.item"))}</th><th>${escapeHtml(t("inspect.value"))}</th></tr></thead>
      <tbody>${body}</tbody>
    </table>
  </div>`;
}

function inspectCardHtml(payload) {
  const view = inspectModel(payload);
  const packages = view.orderables.length
    ? `<p class="other-packages"><b>${escapeHtml(t("inspect.orderables"))}</b><br>${view.orderables.map((line) => escapeHtml(line)).join("<br>")}</p>`
    : "";
  return `
    <article class="card inspect-card">
      <div class="card-head">
        <strong>${escapeHtml(view.partNumber)}</strong>
        <a class="st-link" href="${escapeHtml(view.stUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("stCom"))}</a>
      </div>
      <p class="status-banner is-${escapeHtml(view.status.kind)}">${escapeHtml(view.status.text)}</p>
      ${view.description ? `<p class="lead-copy">${escapeHtml(view.description)}</p>` : ""}
      ${view.sampleNote ? `<p class="decision">${escapeHtml(view.sampleNote)}</p>` : ""}
      ${inspectSpecTable(view.tableRows)}
      ${packages}
      <p class="meta">${escapeHtml(view.disclaimer)}</p>
    </article>`;
}

function shortlistModel(item, index, mode) {
  return {
    rank: index + 1,
    partNumber: item.part_number,
    score: item.score,
    stUrl: stProductUrl(item.part_number, item.rpn || item.reference),
    status: lifecycleStatus(item.status),
    facts: factEntries(item.facts, SHORTLIST_KEYS),
    evidenceTitle: mode === "competitor" ? t("evidence.compare") : t("evidence.match"),
    matchLines: matchLines(item, mode),
    otherPackages: item.other_packages || [],
    decisionNote: item.decision_note || "",
  };
}
