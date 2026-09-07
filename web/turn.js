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

function setFollowupContext(kind, payload) {
  session.context = kind;
  const chips = $("followup-chips");
  const notes = $("followup-notes");
  const box = $("followup-text");
  const followup = $("followup");
  if (followup) followup.hidden = false;
  const items = kind === "inspect" ? inspectChips(payload) : shortlistChips();
  if (chips) {
    chips.innerHTML = items
      .map((item) => `<button type="button" data-q="${escapeHtml(item.q)}">${escapeHtml(item.label)}</button>`)
      .join("");
  }
  if (box) {
    box.placeholder = kind === "inspect"
      ? "例如：推荐 Flash 更大的；查看 STM32G474RET3；替换 NXP MK64FN1M0VLL12。"
      : "例如：为什么是这三颗；再加 USB；替换 NXP MK64FN1M0VLL12。";
  }
  if (notes) {
    notes.textContent = kind === "inspect"
      ? "可按这颗规格再推荐、换一颗订货号，或一句话对照竞品。不承诺价格和交期。"
      : "可问当前候选，也可改规格重新推荐或对照竞品。不承诺价格和交期。";
  }
}

function shortlistChips() {
  return [
    { q: "为什么是这三颗？", label: "为什么是这三颗" },
    { q: "这三颗有什么差别？", label: "有什么差别" },
    { q: "再加 USB", label: "再加 USB" },
  ];
}

function inspectChips(payload) {
  const part = payload && payload.part_number ? String(payload.part_number) : "";
  const facts = (payload && payload.normalized) || {};
  const bits = [];
  if (facts.frequency_mhz) bits.push(`主频至少 ${facts.frequency_mhz} MHz`);
  if (facts.flash_kb) bits.push(`Flash 至少 ${facts.flash_kb} KB`);
  const packageName = String(facts.package_type || facts.package || "").split(" ")[0];
  if (packageName) bits.push(packageName);
  const nearby = bits.length ? bits.join("，") : (part ? `按 ${part} 的规格推荐相近 STM32` : "推荐相近 STM32");
  const chips = [{ q: nearby, label: "推荐相近料" }];
  if (part) chips.push({ q: `这颗 ${part} 适合做什么？`, label: "这颗适合做什么" });
  return chips;
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
    delete thread.dataset.seeded;
  }
  const panel = $("must-panel");
  if (panel) panel.open = true;
  session.candidates = [];
  session.history = [];
  session.context = "";
}

function appendBubble(role, text) {
  const thread = $("thread");
  if (!thread || !text) return;
  thread.hidden = false;
  const bubble = document.createElement("div");
  bubble.className = `bubble is-${role}`;
  bubble.textContent = text;
  thread.appendChild(bubble);
  thread.scrollTop = thread.scrollHeight;
}

function rememberShortlist(payload) {
  const page = document.querySelector(".page");
  if (page) page.classList.add("has-results");
  const panel = $("must-panel");
  if (panel) panel.open = true;
  session.candidates = slimCandidates(payload.recommendations || []);
  setFollowupContext("shortlist", payload);
  const thread = $("thread");
  if (thread && !thread.dataset.seeded) {
    const typed = $("nl-text") && $("nl-text").value.trim();
    appendBubble("user", typed || "已按硬约束推荐。");
    appendBubble("assistant", payload.answer || "已给出最多三颗候选。可继续问，或改硬约束、对照竞品。");
    thread.dataset.seeded = "1";
  }
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
  session.candidates = payload && payload.found
    ? [{
        part_number: payload.part_number,
        facts: payload.normalized || {},
        matches: [],
        risks: [],
      }]
    : [];
  setFollowupContext("inspect", payload);
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
  if (!seed) appendBubble("user", cleaned);
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
      appendBubble("assistant", payload.answer || "");
      renderInspect(payload.inspect);
    } else if (payload.recommendations) {
      if (seed) {
        const thread = $("thread");
        if (thread) delete thread.dataset.seeded;
      }
      renderCards(payload);
      if (!seed && payload.answer) appendBubble("assistant", payload.answer);
    } else if (payload.answer) {
      appendBubble("assistant", payload.answer);
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
const followupChips = $("followup-chips");
if (followupChips) {
  followupChips.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button || !button.dataset.q) return;
    askEngine(button.dataset.q);
  });
}
