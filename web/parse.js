function minValue(constraint) {
  if (constraint && typeof constraint === "object" && constraint.min != null) return constraint.min;
  return "";
}

function maxValue(constraint) {
  if (constraint && typeof constraint === "object" && constraint.max != null) return constraint.max;
  return "";
}

function applyRecommendDraft(draft) {
  const form = $("form-requirements");
  if (!form || !draft) return;
  const must = draft.must || {};
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
    if (!form.elements[name]) return;
    const next = minValue(must[name]);
    if (next !== "" || Object.prototype.hasOwnProperty.call(must, name)) {
      form.elements[name].value = next;
    }
  });
  if (must.pin_count) form.elements.pin_count.value = maxValue(must.pin_count);
  const packageType = Array.isArray(must.package_type) ? must.package_type[0] : "";
  if (packageType) form.elements.package_type.value = packageType;
  if (draft.application) form.elements.application.value = draft.application;
  if (draft.unknown_policy) form.elements.unknown_policy.value = draft.unknown_policy;
  const notes = (draft.notes || []).join(" ");
  const notesEl = $("nl-notes");
  if (notesEl && notes) {
    notesEl.textContent = notes;
    notesEl.dataset.source = "parse";
  }
}
