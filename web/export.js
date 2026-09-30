function exportModel(payload) {
  const request = (payload && payload.request) || {};
  const must = request.must || (payload && payload.must) || {};
  const compact = Boolean(request.compact_package || (payload && payload.compact_package));
  const constraints = exportConstraintText(must, compact);
  const rows = ((payload && payload.recommendations) || []).map((item) => {
    const facts = item.facts || {};
    const part = item.part_number || "";
    return {
      part,
      score: item.score == null ? "" : item.score,
      package: facts.package || facts.package_type || "",
      pins: facts.pin_count == null ? "" : facts.pin_count,
      freq: facts.frequency_mhz == null ? "" : facts.frequency_mhz,
      flash: facts.flash_kb == null ? "" : facts.flash_kb,
      ram: facts.ram_kb == null ? "" : facts.ram_kb,
      status: item.status || "",
      constraints,
      url: typeof stProductUrl === "function" ? stProductUrl(part, item.rpn) : "",
    };
  });
  return { rows };
}

function exportConstraintText(must, compact) {
  const bits = [];
  Object.keys(must || {}).forEach((key) => {
    const value = must[key];
    if (value && typeof value === "object" && value.min != null) bits.push(`${key}≥${value.min}`);
    else if (value && typeof value === "object" && value.max != null) bits.push(`${key}≤${value.max}`);
    else if (Array.isArray(value) && value.length) bits.push(String(value[0]));
  });
  if (compact) bits.push("compact");
  return bits.join("; ");
}

function exportBarHtml(payload) {
  const json = JSON.stringify(exportModel(payload)).replace(/</g, "\\u003c");
  return `<div class="export-bar"><button type="button" data-export="copy">${escapeHtml(t("export.copy"))}</button><button type="button" data-export="csv">${escapeHtml(t("export.csv"))}</button><pre class="export-data" hidden>${escapeHtml(json)}</pre></div>`;
}

function exportHeaders() {
  return [
    t("export.part"), t("export.score"), t("export.package"), t("export.pins"),
    t("export.freq"), t("export.flash"), t("export.ram"), t("export.status"),
    t("export.constraints"), t("export.url"),
  ];
}

function exportMatrix(model) {
  const header = exportHeaders();
  const lines = (model.rows || []).map((row) => [
    row.part, row.score, row.package, row.pins, row.freq, row.flash, row.ram, row.status, row.constraints, row.url,
  ]);
  return [header].concat(lines);
}

function csvCell(value) {
  return `"${String(value == null ? "" : value).replaceAll("\"", "\"\"")}"`;
}

function readExportModel(node) {
  const root = node.closest(".round") || node.closest("#results");
  const script = root && root.querySelector(".export-data");
  if (!script) return null;
  try {
    return JSON.parse(script.textContent || "");
  } catch (error) {
    return null;
  }
}

async function copyExport(model) {
  const text = exportMatrix(model).map((line) => line.join("\t")).join("\n");
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

function downloadExport(model) {
  const csv = `\uFEFF${exportMatrix(model).map((line) => line.map(csvCell).join(",")).join("\n")}`;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 16).replace(/[-:]/g, "").replace("T", "-");
  link.href = URL.createObjectURL(blob);
  link.download = `stm32-shortlist-${stamp}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-export]");
  if (!button) return;
  const model = readExportModel(button);
  if (!model || !model.rows || !model.rows.length) {
    setBanner(t("export.empty"), true);
    return;
  }
  try {
    if (button.getAttribute("data-export") === "csv") downloadExport(model);
    else await copyExport(model);
    setBanner(t("export.done"), false);
  } catch (error) {
    setBanner(t("export.failed"), true);
  }
});
