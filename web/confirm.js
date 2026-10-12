const CONFIRM_CACHE = "st-mcu-confirmed-specs";

function attrText(value) {
  return escapeHtml(value).replaceAll("\"", "&quot;");
}

function httpsUrl(value) {
  try {
    const parsed = new URL(String(value || ""));
    return parsed.protocol === "https:" ? parsed.href : "";
  } catch (error) {
    return "";
  }
}

function readConfirmed(part) {
  try {
    const all = JSON.parse(localStorage.getItem(CONFIRM_CACHE) || "{}");
    const row = all[String(part || "").toUpperCase()];
    return row && typeof row === "object" ? row : null;
  } catch (error) {
    return null;
  }
}

function writeConfirmed(part, specs, sourceUrl) {
  try {
    const all = JSON.parse(localStorage.getItem(CONFIRM_CACHE) || "{}");
    const keys = Object.keys(all);
    while (keys.length > 30) delete all[keys.shift()];
    all[String(part || "").toUpperCase()] = {
      specs,
      source_url: sourceUrl || "",
      confirmed_at: typeof stampNow === "function" ? stampNow() : "",
    };
    localStorage.setItem(CONFIRM_CACHE, JSON.stringify(all));
  } catch (error) {
    /* private mode or a full disk */
  }
}

function confirmFieldHtml(field, cached) {
  let value = field.value == null ? "" : String(field.value);
  let prior = "";
  if (!value && cached && cached.specs && cached.specs[field.key]) {
    value = String(cached.specs[field.key]);
    prior = cached.confirmed_at || "";
  }
  const url = httpsUrl(field.url);
  let source = "";
  if (field.raw) {
    const link = url ? ` <a href="${attrText(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>` : "";
    source = `<p class="confirm-src">${escapeHtml(t("confirm.raw"))} ${escapeHtml(field.raw)}${link}</p>`;
  } else if (prior) {
    source = `<p class="confirm-src">${escapeHtml(t("confirm.prior", { when: prior }))}</p>`;
  }
  const mode = field.key === "package" ? "text" : "decimal";
  return `<label class="confirm-field"><span>${escapeHtml(field.label || "")}</span><input name="${attrText(field.key)}" value="${attrText(value)}" inputmode="${mode}" maxlength="40">${source}</label>`;
}

function confirmHtml(question, card, answer) {
  const part = card.part_number || "";
  const cached = readConfirmed(part);
  const fields = (card.fields || []).map((field) => confirmFieldHtml(field, cached)).join("");
  return `<form class="confirm-card"><p>${escapeHtml(answer || "")}</p><p><b>${escapeHtml(part)}</b></p><input type="hidden" name="question" value="${attrText(question)}"><input type="hidden" name="part_number" value="${attrText(part)}"><input type="hidden" name="source_url" value="${attrText(httpsUrl(card.source_url))}">${fields}<button type="submit">${escapeHtml(t("confirm.submit"))}</button></form>`;
}

function renderConfirmCard(question, card, answer) {
  const results = $("results");
  if (results) results.innerHTML = "";
  const brief = $("brief");
  if (brief) brief.hidden = true;
  prependRound(question, confirmHtml(question, card || {}, answer));
}

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!form || !form.classList || !form.classList.contains("confirm-card")) return;
  event.preventDefault();
  const specs = {};
  ["frequency_mhz", "flash_kb", "ram_kb", "package", "i2c"].forEach((key) => {
    const input = form.elements[key];
    if (!input) return;
    const value = String(input.value || "").trim();
    if (value) specs[key] = value;
  });
  if (!Object.keys(specs).length) {
    setBanner(t("confirm.needOne"), true);
    return;
  }
  const part = form.elements.part_number.value;
  const source = form.elements.source_url.value;
  writeConfirmed(part, specs, source);
  askEngine(form.elements.question.value, {
    confirmed: { part_number: part, source_url: source, specs },
  });
});
