const session = {
  candidates: [],
  history: [],
  context: "",
  view: "",
  payload: null,
};

function slimCandidates(items) {
  return (items || []).slice(0, 3).map((item) => ({
    part_number: item.part_number,
    score: item.score,
    facts: item.facts || {},
    matches: (item.matches || item.comparisons || []).slice(0, 8),
    risks: (item.risks || []).slice(0, 8),
  }));
}

function splitParagraphs(text) {
  const raw = String(text || "").trim();
  if (!raw) return [];
  const blocks = raw.split(/\n\s*\n/).map((item) => item.replace(/\s+/g, " ").trim()).filter(Boolean);
  if (blocks.length > 1) return blocks;
  return raw.split(/\n/).map((item) => item.trim()).filter(Boolean);
}

function briefTitle(payload) {
  const typed = ($("nl-text") && $("nl-text").value.trim())
    || ($("followup-text") && $("followup-text").value.trim())
    || "";
  if (typed) return typed.length > 72 ? `${typed.slice(0, 70)}…` : typed;
  if (payload && payload.mode === "competitor") return t("brief.compare");
  return t("brief.analysis");
}

function fillParagraphs(node, text) {
  if (!node) return;
  node.innerHTML = splitParagraphs(text)
    .map((item) => `<p>${escapeHtml(item)}</p>`)
    .join("");
}

function fallbackAnswer(payload) {
  const names = ((payload && payload.recommendations) || [])
    .map((item) => item.part_number)
    .filter(Boolean)
    .join(getLang() === "en" ? ", " : "、");
  if (!names) return "";
  return t("fallback.shortlist", { names });
}

function showBrief(payload, title) {
  const brief = $("brief");
  const text = (payload && payload.answer) || fallbackAnswer(payload);
  if (!brief || !text) return;
  $("brief-title").textContent = title || briefTitle(payload);
  fillParagraphs($("brief-body"), text);
  brief.hidden = false;
}

function appendTurn(question, answer) {
  const thread = $("thread");
  if (!thread || !answer) return;
  thread.hidden = false;
  const block = document.createElement("article");
  block.className = "turn";
  block.innerHTML = `<h3 class="turn-q">${escapeHtml(question)}</h3><div class="turn-a"></div>`;
  fillParagraphs(block.querySelector(".turn-a"), answer);
  thread.appendChild(block);
  const pane = document.querySelector(".workspace-read");
  if (pane) pane.scrollTop = pane.scrollHeight;
}

function showFollowup(kind) {
  session.context = kind;
  const followup = $("followup");
  if (followup) followup.hidden = false;
  const box = $("followup-text");
  const notes = $("followup-notes");
  if (box) {
    box.placeholder = kind === "inspect" ? t("followup.placeholderInspect") : t("followup.placeholder");
  }
  if (notes) notes.textContent = t("followup.notes");
}

function resetWorkspace() {
  const page = document.querySelector(".page");
  if (page) page.classList.remove("has-results");
  const followup = $("followup");
  if (followup) followup.hidden = true;
  const thread = $("thread");
  if (thread) {
    thread.innerHTML = "";
    thread.hidden = true;
  }
  const brief = $("brief");
  if (brief) {
    brief.hidden = true;
    $("brief-title").textContent = "";
    $("brief-body").innerHTML = "";
  }
  const panel = $("must-panel");
  if (panel) panel.open = true;
  session.candidates = [];
  session.history = [];
  session.context = "";
  session.view = "";
  session.payload = null;
}

function rememberShortlist(payload) {
  const page = document.querySelector(".page");
  if (page) page.classList.add("has-results");
  const panel = $("must-panel");
  if (panel) panel.open = false;
  session.candidates = slimCandidates(payload.recommendations || []);
  session.view = "cards";
  session.payload = payload;
  showFollowup("shortlist");
  showBrief(payload);
}

function paintCurrentResults() {
  if (session.view === "cards" && session.payload) paintCards(session.payload);
  else if (session.view === "inspect" && session.payload) paintInspect(session.payload);
}

const _clearResults = clearResults;
clearResults = function clearResultsAndWorkspace() {
  _clearResults();
  resetWorkspace();
};

const _renderCards = renderCards;
renderCards = function renderCardsWithFollowup(payload) {
  _renderCards(payload);
  rememberShortlist(payload);
};

const _renderInspect = renderInspect;
renderInspect = function renderInspectInPane(payload) {
  _renderInspect(payload);
  const page = document.querySelector(".page");
  if (page) page.classList.add("has-results");
  const panel = $("must-panel");
  if (panel) panel.open = false;
  session.view = "inspect";
  session.payload = payload;
  session.candidates = payload && payload.found
    ? [{
        part_number: payload.part_number,
        facts: payload.normalized || {},
        matches: [],
        risks: [],
      }]
    : [];
  showFollowup("inspect");
};

async function askEngine(text, options) {
  const cleaned = String(text || "").trim();
  const seed = Boolean(options && options.seed);
  if (cleaned.length < 2) {
    setBanner(t("needPrompt"), true);
    return;
  }
  const form = $("form-requirements");
  try {
    const datasheet = typeof attachDatasheetIfAny === "function" ? await attachDatasheetIfAny() : null;
    setBanner(t("processing"), false);
    const replay = Boolean(options && options.replay);
    const prior = replay ? session.history.slice(0, -1) : session.history.slice();
    if (!replay) session.history = prior.concat(cleaned).slice(-4);
    const body = {
      text: cleaned,
      must: collectMust(form),
      application: form.elements.application.value || null,
      unknown_policy: form.elements.unknown_policy.value || "allow_risk",
      candidates: session.candidates,
      history: prior,
      lang: getLang(),
    };
    if (datasheet) body.datasheet = datasheet;
    const response = await fetch("/api/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await parseResponse(response);
    if (payload.must) {
      applyRecommendDraft({
        must: payload.must,
        application: payload.application || "",
        unknown_policy: payload.unknown_policy || "allow_risk",
        notes: payload.notes || [],
        source: payload.source,
      });
    }
    if (payload.inspect) {
      if (!seed) appendTurn(cleaned, payload.answer || "");
      renderInspect(payload.inspect);
    } else if (Array.isArray(payload.recommendations)) {
      renderCards(payload);
    } else if (payload.answer) {
      appendTurn(cleaned, payload.answer);
    }
    setBanner("", false);
    if ($("followup-text")) $("followup-text").value = "";
  } catch (error) {
    setBanner(error.message, true);
  }
}

if (typeof onLangChange === "function") {
  onLangChange(() => {
    const mode = document.querySelector(".mode.is-active");
    const current = mode && mode.dataset.mode;
    if (current === "inspect") {
      const part = $("inspect-part") && $("inspect-part").value.trim();
      if (part && $("form-inspect") && typeof $("form-inspect").requestSubmit === "function") {
        $("form-inspect").requestSubmit();
      }
      return;
    }
    const last = session.history[session.history.length - 1];
    if (last) askEngine(last, { seed: true, replay: true });
  });
}

const followupSend = $("followup-send");
if (followupSend) {
  followupSend.addEventListener("click", () => askEngine($("followup-text").value));
}
const followupText = $("followup-text");
if (followupText) {
  followupText.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      askEngine(followupText.value);
    }
  });
}
