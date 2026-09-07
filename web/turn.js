const session = {
  candidates: [],
  history: [],
  context: "",
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
  if (payload && payload.mode === "competitor") return "竞品对照短名单";
  return "分析结论";
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
    .join("、");
  if (!names) return "";
  return `当前短名单是 ${names}。规格见下方卡片。\n\n这是短名单，不是设计签核。封装引脚、外设并发、认证、价格和供货须核对当前 datasheet。`;
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
    box.placeholder = kind === "inspect"
      ? "例如：推荐 Flash 更大的；查看 STM32G474RET3；替换某厂订货号。"
      : "例如：再加 USB；相近料从 H5 里找；替换某厂订货号。";
  }
  if (notes) {
    notes.textContent = "不承诺价格和交期。硬约束可点上方再改。";
  }
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
}

function rememberShortlist(payload) {
  const page = document.querySelector(".page");
  if (page) page.classList.add("has-results");
  const panel = $("must-panel");
  if (panel) panel.open = false;
  session.candidates = slimCandidates(payload.recommendations || []);
  showFollowup("shortlist");
  showBrief(payload);
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
    setBanner("请先写一句需求、竞品对照或问题。", true);
    return;
  }
  const form = $("form-requirements");
  setBanner("正在处理…", false);
  const prior = session.history.slice();
  session.history = prior.concat(cleaned).slice(-4);
  try {
    const response = await fetch("/api/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: cleaned,
        must: collectMust(form),
        application: form.elements.application.value || null,
        unknown_policy: form.elements.unknown_policy.value || "allow_risk",
        candidates: session.candidates,
        history: prior,
      }),
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
    } else if (payload.recommendations) {
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
