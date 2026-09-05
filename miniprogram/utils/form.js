const facts = require("./facts");

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function collectMust(fields) {
  const must = {};
  ["frequency_mhz", "flash_kb", "ram_kb", "temperature_max_c", "fdcan", "usb", "motor_timers", "hrtim"].forEach((name) => {
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
  ["frequency_mhz", "flash_kb", "ram_kb", "pin_count", "fdcan", "usb", "motor_timers", "hrtim"].forEach((name) => {
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
  const mode = payload.mode === "competitor" ? "competitor" : "requirements";
  return (payload.recommendations || []).map((item, index) => facts.shortlistModel(item, index, mode));
}

function applyRecommendDraft(fields, draft, applications, packages, policies) {
  const must = draft.must || {};
  const rec = { ...fields };
  [
    "frequency_mhz",
    "flash_kb",
    "ram_kb",
    "temperature_max_c",
    "fdcan",
    "usb",
    "motor_timers",
    "hrtim",
  ].forEach((name) => {
    const constraint = must[name];
    rec[name] = constraint && constraint.min != null ? String(constraint.min) : "";
  });
  rec.pin_count = must.pin_count && must.pin_count.max != null ? String(must.pin_count.max) : "";
  const packageType = Array.isArray(must.package_type) ? must.package_type[0] : "";
  const packageIndex = Math.max(0, packages.findIndex((item) => item.id === packageType));
  const applicationIndex = Math.max(0, applications.findIndex((item) => item.id === (draft.application || "")));
  const policyId = draft.unknown_policy || "allow_risk";
  const policyIndex = Math.max(0, policies.findIndex((item) => item.id === policyId));
  const notes = (draft.notes || []).join(" ");
  return { rec, packageIndex, applicationIndex, policyIndex, notes };
}

function toInspectCard(payload) {
  return facts.inspectModel(payload);
}

module.exports = {
  numberOrNull,
  collectMust,
  collectSpecs,
  factChips,
  toCards,
  applyRecommendDraft,
  toInspectCard,
};
