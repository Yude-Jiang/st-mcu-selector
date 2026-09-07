function suggestKind(kind) {
  const raw = String(kind || "");
  if (raw === "订货号" || raw === "orderable") return t("suggest.orderable");
  return t("suggest.series");
}

function bindPartSuggest(input, list) {
  if (!input || !list) return;
  let timer = 0;
  let items = [];
  let active = -1;

  function hide() {
    list.hidden = true;
    list.innerHTML = "";
    active = -1;
    items = [];
    input.setAttribute("aria-expanded", "false");
  }

  function render() {
    if (!items.length) {
      hide();
      return;
    }
    list.innerHTML = items.map((item, index) => `
      <li role="option" data-index="${index}" class="${index === active ? "is-active" : ""}">
        <span class="suggest-value">${escapeHtml(item.value)}</span>
        <span class="suggest-kind">${escapeHtml(suggestKind(item.kind))}</span>
      </li>`).join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function fill(value) {
    input.value = value;
    hide();
    input.focus();
  }

  async function load(query) {
    const needle = String(query || "").replace(/[^A-Za-z0-9]/g, "");
    if (needle.length < 2) {
      hide();
      return;
    }
    try {
      const response = await fetch(`/api/suggest?q=${encodeURIComponent(needle)}&limit=12`);
      if (!response.ok) {
        hide();
        return;
      }
      const payload = await response.json();
      items = payload.items || [];
      active = items.length ? 0 : -1;
      render();
    } catch (error) {
      hide();
    }
  }

  input.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => load(input.value), 180);
  });
  input.addEventListener("keydown", (event) => {
    if (list.hidden || !items.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      active = Math.min(active + 1, items.length - 1);
      render();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      active = Math.max(active - 1, 0);
      render();
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      fill(items[active].value);
    } else if (event.key === "Escape") {
      hide();
    }
  });
  list.addEventListener("mousedown", (event) => {
    const row = event.target.closest("li");
    if (!row) return;
    event.preventDefault();
    const item = items[Number(row.dataset.index)];
    if (item) fill(item.value);
  });
  input.addEventListener("blur", () => window.setTimeout(hide, 120));
}

bindPartSuggest(
  document.querySelector("#form-inspect input[name='part_number']"),
  $("inspect-suggest-list"),
);
