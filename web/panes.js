const panes = {};

function snapshotPane(mode) {
  if (!mode) return;
  const page = document.querySelector(".page");
  const panel = $("must-panel");
  const box = $("followup-text");
  panes[mode] = {
    results: $("results") ? $("results").innerHTML : "",
    briefTitle: $("brief-title") ? $("brief-title").textContent : "",
    briefBody: $("brief-body") ? $("brief-body").innerHTML : "",
    briefHidden: !$("brief") || $("brief").hidden,
    thread: $("thread") ? $("thread").innerHTML : "",
    threadHidden: !$("thread") || $("thread").hidden,
    followupHidden: !$("followup") || $("followup").hidden,
    followupValue: box ? box.value : "",
    mustOpen: panel ? panel.open : true,
    hasResults: Boolean(page && page.classList.contains("has-results")),
    view: session.view,
    payload: session.payload,
    session: {
      candidates: session.candidates.slice(),
      history: session.history.slice(),
      context: session.context,
    },
  };
}

function emptyReadout() {
  const page = document.querySelector(".page");
  if (page) page.classList.remove("has-results");
  if ($("results")) $("results").innerHTML = "";
  const brief = $("brief");
  if (brief) {
    brief.hidden = true;
    if ($("brief-title")) $("brief-title").textContent = "";
    if ($("brief-body")) $("brief-body").innerHTML = "";
  }
  const thread = $("thread");
  if (thread) {
    thread.innerHTML = "";
    thread.hidden = true;
  }
  const followup = $("followup");
  if (followup) followup.hidden = true;
  session.candidates = [];
  session.history = [];
  session.context = "";
  session.view = "";
  session.payload = null;
}

function restorePane(mode) {
  const saved = panes[mode];
  if (!saved) {
    emptyReadout();
    return;
  }
  session.candidates = saved.session.candidates.slice();
  session.history = saved.session.history.slice();
  session.context = saved.session.context;
  session.view = saved.view || "";
  session.payload = saved.payload;
  if (saved.view === "cards" && saved.payload) paintCards(saved.payload);
  else if (saved.view === "inspect" && saved.payload) paintInspect(saved.payload);
  else if ($("results")) $("results").innerHTML = saved.results;
  if ($("brief-title")) $("brief-title").textContent = saved.briefTitle;
  if ($("brief-body")) $("brief-body").innerHTML = saved.briefBody;
  if ($("brief")) $("brief").hidden = saved.briefHidden;
  if ($("thread")) {
    $("thread").innerHTML = saved.thread;
    $("thread").hidden = saved.threadHidden;
  }
  const page = document.querySelector(".page");
  if (page) page.classList.toggle("has-results", saved.hasResults);
  const followup = $("followup");
  const box = $("followup-text");
  if (followup) followup.hidden = saved.followupHidden;
  if (box) box.value = saved.followupValue;
  if (followup && !followup.hidden) showFollowup(session.context);
  const panel = $("must-panel");
  if (panel) panel.open = saved.mustOpen;
}

const _showMode = showMode;
showMode = function persistPanes(mode) {
  const active = document.querySelector(".mode.is-active");
  const current = active && active.dataset.mode;
  if (!current || !mode || current === mode) {
    _showMode(mode);
    return;
  }
  snapshotPane(current);
  _showMode(mode);
  restorePane(mode);
  setBanner("", false);
};

onLangChange(() => {
  if (typeof applyHealthCopy === "function") applyHealthCopy();
  if (typeof showAttachedName === "function" && typeof attachedDatasheetFile === "function") {
    showAttachedName(attachedDatasheetFile());
  }
  const followup = $("followup");
  if (followup && !followup.hidden) showFollowup(session.context);
  paintCurrentResults();
});
