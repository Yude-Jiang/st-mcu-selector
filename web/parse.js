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
    form.elements[name].value = minValue(must[name]);
  });
  form.elements.pin_count.value = maxValue(must.pin_count);
  const packageType = Array.isArray(must.package_type) ? must.package_type[0] : "";
  form.elements.package_type.value = packageType || "";
  form.elements.application.value = draft.application || "";
  form.elements.unknown_policy.value = draft.unknown_policy || "allow_risk";
  const notes = (draft.notes || []).join(" ");
  const fallback = draft.source === "model"
    ? "已填入表单，请核对后再给出短名单。"
    : "已按关键词填入表单，请核对后再给出短名单。";
  const notesEl = $("nl-notes");
  notesEl.textContent = notes || fallback;
  notesEl.dataset.source = "parse";
}

const nlFill = $("nl-fill");
if (nlFill) {
  nlFill.addEventListener("click", async () => {
    const text = $("nl-text").value.trim();
    if (text.length < 4) {
      setBanner("请先写一句可核对的需求。", true);
      return;
    }
    setBanner("正在把需求改写成表单…", false);
    try {
      const payload = await postJson("/api/parse-requirements", { text });
      applyRecommendDraft(payload);
      setBanner("", false);
    } catch (error) {
      setBanner(error.message, true);
    }
  });
}
