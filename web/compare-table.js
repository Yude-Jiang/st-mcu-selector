const TABLE_KEYS = [
  "core", "frequency_mhz", "flash_kb", "ram_kb", "package", "package_type",
  "pin_count", "temperature_max_c", "fdcan", "usb", "motor_timers", "hrtim",
];
const TABLE_RATIO_KEYS = { frequency_mhz: true, flash_kb: true, ram_kb: true };

function tableTimes(stValue, otherValue) {
  const stNum = Number(stValue);
  const otherNum = Number(otherValue);
  if (!Number.isFinite(stNum) || !Number.isFinite(otherNum) || stNum <= 0 || otherNum <= 0) {
    return "";
  }
  const ratio = Math.max(stNum, otherNum) / Math.min(stNum, otherNum);
  if (ratio < 1.08) return t("table.near");
  const times = ratio >= 10 ? String(Math.round(ratio)) : String(ratio.toFixed(1)).replace(/\.0$/, "");
  if (otherNum > stNum) return t("table.compHigher", { times });
  if (stNum > otherNum) return t("table.stHigher", { times });
  return t("table.same");
}

function tableCell(key, value) {
  if (!hasFactValue(value)) return t("table.missing");
  return formatFactValue(key, value);
}

function competitorSpecValue(specs, key) {
  if (key === "package") return specs.package_type || specs.package;
  return specs[key];
}

function firstFact(items, key) {
  const first = items[0] && items[0].facts;
  return first ? first[key] : undefined;
}

function attachApplication(payload) {
  const form = document.getElementById("form-requirements");
  if (payload && !payload.application && form && form.elements.application && form.elements.application.value) {
    payload.application = form.elements.application.value;
  }
  return payload;
}

function applicationBannerHtml(payload) {
  const application = payload && payload.application;
  if (!application) return "";
  const label = t(`opt.${application === "motor_control" ? "motor" : application === "power_conversion" ? "power" : application === "industrial_control" ? "industrial" : application}`) || application;
  const named = {
    motor_control: t("opt.motor"),
    power_conversion: t("opt.power"),
    bms: t("opt.bms"),
    industrial_control: t("opt.industrial"),
    iot: t("opt.iot"),
  }[application];
  return `<p class="app-banner">${escapeHtml(t("app.banner", { app: named || label }))}</p>`;
}

function compareTableHtml(payload) {
  attachApplication(payload);
  const banner = applicationBannerHtml(payload);
  if (!payload || payload.mode !== "competitor" || !payload.compare) return banner;
  const specs = payload.compare.specs || {};
  const items = (payload.recommendations || []).slice(0, 3);
  const rows = TABLE_KEYS.filter((key) => {
    const other = competitorSpecValue(specs, key);
    return hasFactValue(other) || items.some((item) => hasFactValue((item.facts || {})[key]));
  });
  if (!rows.length) return banner;
  const competitorName = [payload.compare.manufacturer, payload.compare.part_number].filter(Boolean).join(" ") || t("table.competitor");
  const head = [
    `<th>${escapeHtml(t("table.item"))}</th>`,
    `<th>${escapeHtml(competitorName)}</th>`,
    ...items.map((item) => `<th>${escapeHtml(item.part_number || "")}</th>`),
    `<th>${escapeHtml(t("table.verdict"))}</th>`,
  ].join("");
  const body = rows.map((key) => {
    const other = competitorSpecValue(specs, key);
    const stFirst = firstFact(items, key);
    const verdict = TABLE_RATIO_KEYS[key] ? tableTimes(stFirst, other) : "";
    const cells = [
      `<th>${escapeHtml(factLabel(key))}</th>`,
      `<td>${escapeHtml(tableCell(key, other))}</td>`,
      ...items.map((item) => `<td>${escapeHtml(tableCell(key, (item.facts || {})[key]))}</td>`),
      `<td>${escapeHtml(verdict)}</td>`,
    ].join("");
    return `<tr>${cells}</tr>`;
  }).join("");
  return `${banner}<div class="compare-table-wrap">
    <h3 class="compare-table-title">${escapeHtml(t("table.title"))}</h3>
    <table class="compare-table">
      <thead><tr>${head}</tr></thead>
      <tbody>${body}</tbody>
    </table>
    <p class="compare-table-note">${escapeHtml(t("table.note"))}</p>
  </div>`;
}
