/* Quillmark style coach. Deterministic suggestions, one accepted edit at a time. */
(function () {
  "use strict";

  var input = document.getElementById("coach-input");
  var meta = document.getElementById("coach-meta");
  var runBtn = document.getElementById("coach-run");
  var scoreBtn = document.getElementById("coach-score");
  var rescoreBtn = document.getElementById("coach-rescore");
  var copyBtn = document.getElementById("coach-copy");
  var result = document.getElementById("coach-result");
  var findingsBox = document.getElementById("coach-findings");
  var summary = document.getElementById("coach-summary");
  var actions = document.getElementById("coach-actions");
  var scoreResult = document.getElementById("coach-score-result");
  var scoreVerdict = document.getElementById("coach-score-verdict");
  var scoreDetail = document.getElementById("coach-score-detail");
  var notice = document.getElementById("coach-notice");
  var noticeText = document.getElementById("coach-notice-text");

  var state = { original: "", edits: [], applied: {}, scores: [] };

  function words(text) {
    return text.trim() ? text.trim().split(/\s+/).length : 0;
  }

  function updateMeta() {
    meta.textContent = words(input.value) + " words";
  }

  function showNotice(message) {
    noticeText.textContent = message;
    notice.hidden = false;
  }

  function hideNotice() {
    notice.hidden = true;
  }

  function busy(button, on, label) {
    button.disabled = on;
    if (on) {
      button.dataset.label = button.textContent;
      button.textContent = label || "Working...";
    } else if (button.dataset.label) {
      button.textContent = button.dataset.label;
    }
  }

  async function postJSON(url, body) {
    var response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (response.status === 202) {
      var ticket = (await response.json()).ticket_id;
      for (;;) {
        await new Promise(function (r) { setTimeout(r, 1500); });
        var poll = await fetch("/api/queue/ticket/" + encodeURIComponent(ticket));
        if (poll.status === 202) continue;
        if (!poll.ok) throw new Error("Queue failed");
        return poll.json();
      }
    }
    if (!response.ok) {
      var detail = "Request failed";
      try { detail = (await response.json()).detail || detail; } catch (e) { /* ignore */ }
      throw new Error(detail);
    }
    return response.json();
  }

  var RULE_LABEL = {
    R1: "Abstract noun",
    R2: "Chained 'de'",
    R3: "Stock connector",
    R4: "Symmetric list",
    R5: "Sentence rhythm",
    R6: "Hedge",
    R7: "No anchor",
    R8: "Filler",
  };

  function render(data) {
    findingsBox.innerHTML = "";
    summary.textContent = data.summary.total === 0
      ? "No patterns from the eight measured rules. That is a good sign, not a guarantee."
      : data.summary.total + " findings (" + data.summary.mechanical + " can be applied mechanically). " +
        Object.keys(data.summary.by_rule).map(function (rule) {
          return (RULE_LABEL[rule] || rule) + " x" + data.summary.by_rule[rule];
        }).join(", ");
    result.hidden = false;
    actions.hidden = data.summary.mechanical === 0;

    data.findings.forEach(function (finding, index) {
      var card = document.createElement("article");
      card.className = "st-panel";
      card.style.marginTop = "0.75rem";

      var head = document.createElement("p");
      head.className = "site-result__host";
      head.textContent = finding.rule + " · " + finding.label;
      card.appendChild(head);

      var quote = document.createElement("p");
      quote.className = "site-result__text";
      quote.textContent = "“" + finding.quote + "”";
      card.appendChild(quote);

      var suggestion = document.createElement("p");
      suggestion.className = "st-field__hint";
      suggestion.textContent = finding.suggestion;
      card.appendChild(suggestion);

      var note = document.createElement("p");
      note.className = "site-result__note";
      note.textContent = finding.note;
      card.appendChild(note);

      if (finding.auto && finding.replacement !== null) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "st-btn st-btn--secondary";
        button.textContent = "Apply";
        button.addEventListener("click", function () {
          applyEdit(finding, button);
        });
        card.appendChild(button);
      }
      findingsBox.appendChild(card);
    });
  }

  async function applyEdit(finding, button) {
    var key = finding.start + ":" + finding.end;
    if (state.applied[key]) return;
    state.edits.push({ start: finding.start, end: finding.end, replacement: finding.replacement });
    button.disabled = true;
    button.textContent = "Applied";
    try {
      var out = await postJSON("/api/coach/apply", { text: state.original, edits: state.edits });
      input.value = out.text;
      updateMeta();
      state.applied[key] = true;
    } catch (error) {
      button.disabled = false;
      button.textContent = "Apply";
      showNotice(error.message);
    }
  }

  async function runCoach() {
    hideNotice();
    var text = input.value.trim();
    if (words(text) < 30) {
      showNotice("Paste at least 30 words: below that, style patterns mean little.");
      return;
    }
    busy(runBtn, true, "Reading...");
    try {
      var data = await postJSON("/api/coach", { text: text });
      state.original = text;
      state.edits = [];
      state.applied = {};
      render(data);
    } catch (error) {
      showNotice(error.message);
    } finally {
      busy(runBtn, false);
    }
  }

  async function scoreText() {
    hideNotice();
    var text = input.value.trim();
    if (words(text) < 30) {
      showNotice("Paste at least 30 words before scoring.");
      return;
    }
    var button = input.value === state.original ? scoreBtn : rescoreBtn;
    busy(button, true, "Scoring...");
    try {
      var report = await postJSON("/api/analyze", { text: text });
      var previous = state.scores.length ? state.scores[state.scores.length - 1] : null;
      state.scores.push(report.overall_score);
      scoreResult.hidden = false;
      scoreVerdict.textContent = report.overall_score + " · " + (report.overall_verdict === "Slop detected" ? "Very strong AI signals" : report.overall_verdict);
      var engines = report.engine_results
        .filter(function (engine) { return engine.score >= 0.7; })
        .sort(function (a, b) { return b.score - a.score; })
        .slice(0, 4)
        .map(function (engine) { return engine.engine_name + " " + engine.score.toFixed(2); });
      var delta = previous === null ? "" :
        " (before: " + previous + ", change " + (report.overall_score - previous).toFixed(1) + ")";
      scoreDetail.textContent = report.engines_flagged + " of " + report.engines_total +
        " engines flagged it" + (engines.length ? "; loudest: " + engines.join(", ") : "") + "." + delta;
    } catch (error) {
      showNotice(error.message);
    } finally {
      busy(button, false);
    }
  }

  input.addEventListener("input", updateMeta);
  runBtn.addEventListener("click", runCoach);
  scoreBtn.addEventListener("click", scoreText);
  rescoreBtn.addEventListener("click", scoreText);
  copyBtn.addEventListener("click", function () {
    navigator.clipboard.writeText(input.value).then(function () {
      copyBtn.textContent = "Copied";
      setTimeout(function () { copyBtn.textContent = "Copy edited text"; }, 1500);
    });
  });

  updateMeta();
})();
