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

function specsToMust(specs) {
  const must = {};
  if (!specs) return must;
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
    if (specs[name] != null) must[name] = { min: specs[name] };
  });
  if (specs.pin_count != null) must.pin_count = { max: specs.pin_count };
  if (specs.package_type) must.package_type = [specs.package_type];
  return must;
}

function datasheetKind(file) {
  const name = String((file && file.name) || "").toLowerCase();
  const type = String((file && file.type) || "").toLowerCase();
  if (type === "application/pdf" || name.endsWith(".pdf")) return "pdf";
  if (type.startsWith("image/") || /\.(png|jpe?g|webp|bmp)$/.test(name)) return "image";
  return "";
}

function attachedDatasheetFile() {
  const input = $("nl-pdf");
  return input && input.files && input.files[0] ? input.files[0] : null;
}

function showAttachedName(file) {
  const label = $("nl-file-name");
  if (!label) return;
  if (!file) {
    label.hidden = true;
    label.textContent = "";
    return;
  }
  label.hidden = false;
  label.textContent = file.name || "已选择文件";
}

function setAttachedFile(file) {
  const input = $("nl-pdf");
  if (!input || !file) return;
  const kind = datasheetKind(file);
  if (!kind) {
    setBanner("请上传 PDF 规格书或清晰截图（PNG / JPG / WebP）。", true);
    return;
  }
  if (file.size > 8 * 1024 * 1024) {
    setBanner("文件请控制在 8 MB 以内。", true);
    return;
  }
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.files = transfer.files;
  showAttachedName(file);
  setBanner("", false);
}

async function attachDatasheetIfAny() {
  const file = attachedDatasheetFile();
  if (!file) return null;
  const kind = datasheetKind(file);
  setBanner(kind === "image" ? "正在识别图片中的规格…" : "正在从规格书抽取规格…", false);
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/parse-datasheet", { method: "POST", body });
  const payload = await parseResponse(response);
  applyRecommendDraft({
    must: specsToMust(payload.specs),
    notes: [payload.source_note].concat(payload.notes || []).filter(Boolean),
  });
  const panel = $("must-panel");
  if (panel) panel.open = true;
  return {
    specs: payload.specs || {},
    part_number: payload.part_number || "",
    manufacturer: payload.manufacturer || "",
    source_note: payload.source_note || "",
    notes: payload.notes || [],
  };
}

(function bindDatasheetDrop() {
  const box = $("nl-drop");
  const input = $("nl-pdf");
  if (!box || !input) return;
  showAttachedName(attachedDatasheetFile());
  input.addEventListener("change", () => {
    const file = attachedDatasheetFile();
    if (file) setAttachedFile(file);
    else showAttachedName(null);
  });
  ["dragenter", "dragover"].forEach((name) => {
    box.addEventListener(name, (event) => {
      event.preventDefault();
      box.classList.add("is-over");
    });
  });
  box.addEventListener("dragleave", (event) => {
    if (!box.contains(event.relatedTarget)) box.classList.remove("is-over");
  });
  box.addEventListener("drop", (event) => {
    event.preventDefault();
    box.classList.remove("is-over");
    const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    if (file) setAttachedFile(file);
  });
  ["dragover", "drop"].forEach((name) => {
    document.addEventListener(name, (event) => {
      if (!event.target.closest || !event.target.closest("#nl-drop")) event.preventDefault();
    });
  });
})();

