const LANG_KEY = "st-mcu-lang";
const i18nHooks = [];
let currentLang = "zh";

function normalizeLang(value) {
  return String(value || "").toLowerCase().startsWith("en") ? "en" : "zh";
}

function readStoredLang() {
  try {
    return normalizeLang(localStorage.getItem(LANG_KEY) || "zh");
  } catch (error) {
    return "zh";
  }
}

function getLang() {
  return currentLang;
}

function t(key, vars) {
  const table = (typeof COPY === "object" && COPY[currentLang]) || {};
  const fallback = (typeof COPY === "object" && COPY.zh) || {};
  let text = table[key] || fallback[key] || key;
  if (vars) {
    Object.keys(vars).forEach((name) => {
      text = text.replaceAll(`{${name}}`, String(vars[name]));
    });
  }
  return text;
}

function setMeta(name, content, attr) {
  const selector = attr === "property"
    ? `meta[property="${name}"]`
    : `meta[name="${name}"]`;
  const node = document.querySelector(selector);
  if (node) node.setAttribute("content", content);
}

function applyTdk() {
  document.documentElement.lang = currentLang === "en" ? "en" : "zh-CN";
  document.title = t("tdk.title");
  setMeta("description", t("tdk.description"));
  setMeta("keywords", t("tdk.keywords"));
  setMeta("og:title", t("tdk.title"), "property");
  setMeta("og:description", t("tdk.description"), "property");
  setMeta("twitter:title", t("tdk.title"));
  setMeta("twitter:description", t("tdk.description"));
}

function applyStaticCopy() {
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.getAttribute("data-i18n-placeholder"));
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    node.setAttribute("aria-label", t(node.getAttribute("data-i18n-aria")));
  });
  document.querySelectorAll(".lang").forEach((button) => {
    const on = button.dataset.lang === currentLang;
    button.classList.toggle("is-active", on);
    button.setAttribute("aria-selected", on ? "true" : "false");
    button.tabIndex = on ? 0 : -1;
  });
}

function applyChrome() {
  applyTdk();
  applyStaticCopy();
  i18nHooks.forEach((fn) => fn());
}

function onLangChange(fn) {
  if (typeof fn === "function") i18nHooks.push(fn);
}

function setLang(lang) {
  const next = normalizeLang(lang);
  currentLang = next;
  try {
    localStorage.setItem(LANG_KEY, next);
  } catch (error) {
    /* ignore quota / private mode */
  }
  applyChrome();
}

function bindLangTabs() {
  document.querySelectorAll(".lang").forEach((button) => {
    button.addEventListener("click", () => setLang(button.dataset.lang));
  });
  document.querySelectorAll(".langs").forEach((list) => {
    const items = [...list.querySelectorAll(".lang")];
    list.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      const current = items.findIndex((tab) => tab.classList.contains("is-active"));
      let next = current;
      if (event.key === "ArrowRight") next = (current + 1) % items.length;
      if (event.key === "ArrowLeft") next = (current - 1 + items.length) % items.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = items.length - 1;
      event.preventDefault();
      setLang(items[next].dataset.lang);
      items[next].focus();
    });
  });
}

currentLang = readStoredLang();
bindLangTabs();
applyTdk();
applyStaticCopy();
