const GATE_KEY = "st-mcu-gate-email";

function isStEmail(value) {
  const email = String(value || "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return false;
  return email.includes("@st.com");
}

function readGateEmail() {
  try {
    return String(sessionStorage.getItem(GATE_KEY) || "");
  } catch (error) {
    return "";
  }
}

function saveGateEmail(email) {
  try {
    sessionStorage.setItem(GATE_KEY, email);
  } catch (error) {
    /* ignore quota / private mode */
  }
}

function showMainApp() {
  const gate = document.getElementById("gate");
  const root = document.getElementById("root");
  if (gate) gate.hidden = true;
  if (root) root.hidden = false;
}

function showGate() {
  const gate = document.getElementById("gate");
  const root = document.getElementById("root");
  if (root) root.hidden = true;
  if (gate) gate.hidden = false;
}

function applyGateCopy() {
  const lead = document.getElementById("gate-lead");
  const input = document.getElementById("gate-email");
  const submit = document.getElementById("gate-submit");
  const hint = document.getElementById("gate-hint");
  const error = document.getElementById("gate-error");
  const title = document.getElementById("gate-title");
  if (title) title.textContent = t("gate.title");
  if (lead) lead.textContent = t("gate.lead");
  if (input) input.placeholder = t("gate.placeholder");
  if (submit) submit.textContent = t("gate.submit");
  if (hint) hint.textContent = t("gate.hint");
  if (error && error.dataset.open === "1") error.textContent = t("gate.error");
}

function bindGate() {
  const form = document.getElementById("gate-form");
  const input = document.getElementById("gate-email");
  const error = document.getElementById("gate-error");
  if (!form || !input) return;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const email = input.value.trim();
    if (!isStEmail(email)) {
      if (error) {
        error.hidden = false;
        error.dataset.open = "1";
        error.textContent = t("gate.error");
      }
      return;
    }
    saveGateEmail(email.toLowerCase());
    if (error) {
      error.hidden = true;
      error.dataset.open = "";
    }
    showMainApp();
  });
}

function startGate() {
  if (isStEmail(readGateEmail())) {
    showMainApp();
  } else {
    showGate();
  }
  bindGate();
  applyGateCopy();
  if (typeof onLangChange === "function") onLangChange(applyGateCopy);
}

startGate();
