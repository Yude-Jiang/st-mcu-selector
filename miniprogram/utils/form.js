const facts = require("./facts");

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function collectMust(fields) {
  const must = {};
  ["frequency_mhz", "flash_kb", "ram_kb", "temperature_max_c", "fdcan"].forEach((name) => {
    const value = numberOrNull(fields[name]);
    if (value !== null) must[name] = { min: value };
  });
  const pins = numberOrNull(fields.pin_count);
  if (pins !== null) must.pin_count = { max: pins };
  if (fields.package_type) must.package_type = [fields.package_type];
  return must;
}

function collectSpecs(fields) {
  const specs = {};
  ["frequency_mhz", "flash_kb", "ram_kb", "pin_count", "fdcan"].forEach((name) => {
    const value = numberOrNull(fields[name]);
    if (value !== null) specs[name] = value;
  });
  const packageType = String(fields.package_type || "").trim();
  if (packageType) specs.package_type = packageType;
  return specs;
}

function factChips(source) {
  return facts.factEntries(source).map((item) => ({
    key: item.key,
    text: `${item.label}: ${item.value}`,
  }));
}

function toCards(payload) {
  const items = payload.recommendations || [];
  return items.map((item, index) => ({
    partNumber: item.part_number,
    score: item.score,
    status: item.status || "",
    rank: index + 1,
    highlight: index === 0,
    facts: factChips(item.facts),
    matches: item.matches || item.comparisons || [],
    risks: item.risks || [],
  }));
}

function toInspectCard(payload) {
  return facts.inspectModel(payload);
}

module.exports = { numberOrNull, collectMust, collectSpecs, factChips, toCards, toInspectCard };
