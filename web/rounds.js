function stampNow() {
  const locale = typeof getLang === "function" && getLang() === "en" ? "en-CA" : "zh-CN";
  return new Intl.DateTimeFormat(locale, {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date());
}

function prependRound(question, bodyHtml) {
  const host = $("rounds");
  if (!host || !bodyHtml) return;
  host.hidden = false;
  const block = document.createElement("article");
  block.className = "round";
  const title = question ? `<h3 class="round-q">${escapeHtml(question)}</h3>` : "";
  block.innerHTML = `<p class="round-time">${escapeHtml(stampNow())}</p>${title}<div class="round-body">${bodyHtml}</div>`;
  if (window.__replaceTopRound && host.firstChild) host.removeChild(host.firstChild);
  window.__replaceTopRound = false;
  host.insertBefore(block, host.firstChild);
  const pane = document.querySelector(".workspace-read");
  if (pane) pane.scrollTop = 0;
}

function hoistResults(question) {
  const briefBody = $("brief-body");
  const results = $("results");
  const parts = [];
  if (briefBody && briefBody.innerHTML.trim()) {
    parts.push(`<div class="brief-body">${briefBody.innerHTML}</div>`);
  }
  if (results && results.innerHTML.trim()) parts.push(results.innerHTML);
  if (!parts.length) return;
  prependRound(question || "", parts.join(""));
  const brief = $("brief");
  if (brief) brief.hidden = true;
  if (results) results.innerHTML = "";
}

const _renderCardsForRounds = renderCards;
renderCards = function renderCardsAsRound(payload) {
  _renderCardsForRounds(payload);
  const question = window.__roundQuestion || (typeof briefTitle === "function" ? briefTitle(payload) : "");
  window.__roundQuestion = "";
  hoistResults(question);
};

appendTurn = function appendTurnOnTop(question, answer) {
  if (!answer) return;
  const holder = document.createElement("div");
  holder.className = "turn-a";
  fillParagraphs(holder, answer);
  prependRound(question, holder.outerHTML);
  const thread = $("thread");
  if (thread) thread.hidden = true;
};
