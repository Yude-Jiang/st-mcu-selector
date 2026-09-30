let lastConstraintKey = "";

function constraintKey(form) {
  const data = new FormData(form);
  return JSON.stringify({
    must: collectMust(form),
    application: String(data.get("application") || ""),
    unknown_policy: String(data.get("unknown_policy") || "allow_risk"),
    compact: Boolean(form.elements.compact_package && form.elements.compact_package.checked),
  });
}

function constraintsUpdated(form) {
  return Boolean(lastConstraintKey) && constraintKey(form) !== lastConstraintKey;
}

function rememberConstraints(form) {
  if (!form) return;
  lastConstraintKey = constraintKey(form);
  if (typeof recordHistory === "function") recordHistory(form);
}

function clearConstraintSnapshot() {
  lastConstraintKey = "";
}

function constraintSummary(form) {
  const must = collectMust(form);
  const en = typeof getLang === "function" && getLang() === "en";
  const bits = [];
  if (must.frequency_mhz) bits.push(`${en ? "Clock" : "主频"}≥${must.frequency_mhz.min}`);
  if (must.flash_kb) bits.push(`Flash≥${must.flash_kb.min}`);
  if (must.ram_kb) bits.push(`RAM≥${must.ram_kb.min}`);
  if (must.pin_count) bits.push(`${en ? "Pins" : "引脚"}≤${must.pin_count.max}`);
  if (must.package_type && must.package_type[0]) bits.push(String(must.package_type[0]));
  if (must.i2c) bits.push(`I2C≥${must.i2c.min}`);
  if (must.usb) bits.push(`USB≥${must.usb.min}`);
  if (must.fdcan) bits.push(`FDCAN≥${must.fdcan.min}`);
  if (must.motor_timers) bits.push(`${en ? "Motor timers" : "电机定时器"}≥${must.motor_timers.min}`);
  if (must.hrtim) bits.push(`HRTIM≥${must.hrtim.min}`);
  if (must.temperature_max_c) bits.push(`${en ? "Temp" : "温度"}≥${must.temperature_max_c.min}`);
  if (form.elements.compact_package && form.elements.compact_package.checked) bits.push(t("field.compact"));
  return bits.join(en ? ", " : "，");
}

async function recommendFromForm(form) {
  const data = new FormData(form);
  window.__roundQuestion = constraintSummary(form);
  const payload = await postJson("/api/recommend", {
    must: collectMust(form),
    application: data.get("application") || null,
    unknown_policy: data.get("unknown_policy") || "allow_risk",
    compact_package: Boolean(form.elements.compact_package && form.elements.compact_package.checked),
    limit: 3,
  });
  setBanner("", false);
  renderCards(payload);
  rememberConstraints(form);
}

async function submitRequirements(form) {
  const text = ($("nl-text") && $("nl-text").value.trim()) || "";
  try {
    if (constraintsUpdated(form)) {
      await recommendFromForm(form);
      return;
    }
    if (text.length >= 4 || (typeof attachedDatasheetFile === "function" && attachedDatasheetFile())) {
      const prompt = text.length >= 2 ? text : t("uploadPrompt");
      if (typeof askEngine === "function") {
        await askEngine(prompt, { seed: true });
        return;
      }
    }
    const compact = Boolean(form.elements.compact_package && form.elements.compact_package.checked);
    const hasConstraint = Object.keys(collectMust(form)).length || compact || form.elements.application.value;
    if (!hasConstraint) {
      setBanner(t("needPrompt"), true);
      return;
    }
    await recommendFromForm(form);
  } catch (error) {
    setBanner(error.message, true);
  }
}
