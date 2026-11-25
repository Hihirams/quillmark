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

  var upload = document.getElementById("coach-file");
  var sourceStatus = document.getElementById("coach-file-status");
  var downloadBtn = document.getElementById("coach-download");
  var state = { original: "", prefix: "", suffix: "", edits: [], applied: {}, filename: "", baseline: null, baselineReport: null, working: false };

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
      for (var attempt = 0; attempt < 120; attempt++) {
        await new Promise(function (r) { setTimeout(r, 1500); });
        var poll = await fetch("/api/queue/ticket/" + encodeURIComponent(ticket));
        if (poll.status === 202) continue;
        if (!poll.ok) throw new Error("Queue failed");
        return poll.json();
      }
      throw new Error("Scoring took too long. Please try again.");
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


  function resetFindings() {
    state.original = "";
    state.edits = [];
    state.applied = {};
    result.hidden = true;
    findingsBox.replaceChildren();
  }

  function refreshControls() {
    var hasText = !!input.value.trim();
    var edited = hasText && state.baseline !== null && input.value.trim() !== state.baseline;
    upload.disabled = state.working;
    input.readOnly = state.working;
    downloadBtn.disabled = state.working || !hasText;
    scoreBtn.disabled = state.working || !hasText;
    runBtn.disabled = state.working || !hasText;
    rescoreBtn.disabled = state.working || !edited;
    copyBtn.disabled = state.working || !hasText;
    actions.hidden = !hasText;
    rescoreBtn.hidden = !edited;
    findingsBox.querySelectorAll("button").forEach(function (button) {
      button.disabled = state.working || button.dataset.applied === "true";
    });
  }

  async function work(button, label, operation) {
    if (state.working) return;
    state.working = true;
    if (button) busy(button, true, label);
    refreshControls();
    hideNotice();
    try { await operation(); }
    catch (error) { showNotice(error.message || "Something went wrong. Please try again."); }
    finally {
      state.working = false;
      if (button) busy(button, false);
      refreshControls();
    }
  }

  async function importFile(file) {
    if (!file || state.working) return;
    try {
      if (!/\.(pdf|docx|txt|md)$/i.test(file.name)) {
        showNotice("Choose a PDF, DOCX, TXT or Markdown file.");
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        showNotice("Files can be up to 10 MB.");
        return;
      }
      if (input.value.trim() && !window.confirm("Replace the draft in this editor? Your original file will not change.")) return;
      await work(null, "", async function () {
        sourceStatus.textContent = "Reading " + file.name + "…";
        try {
          var body = new FormData();
          body.append("file", file);
          var response = await fetch("/api/extract", { method: "POST", body: body });
          var data = await response.json();
          if (!response.ok || typeof data.text !== "string" || !data.text.trim()) {
            throw new Error(data.error || "Quillmark could not extract text from this file.");
          }
          input.value = data.text;
          state.filename = file.name;
          state.baseline = input.value.trim();
          state.baselineReport = null;
          scoreResult.hidden = true;
          resetFindings();
          updateMeta();
          sourceStatus.textContent = "Loaded " + file.name;
        } catch (error) {
          sourceStatus.textContent = state.filename ? "Loaded " + state.filename : "No file loaded";
          throw error;
        }
      });
    } finally {
      upload.value = "";
    }
  }

  async function applyEdit(finding, button) {
    var key = finding.start + ":" + finding.end;
    if (state.applied[key]) return;
    await work(button, "Applying…", async function () {
      var edits = state.edits.concat([{ start: finding.start, end: finding.end, replacement: finding.replacement }]);
      var out = await postJSON("/api/coach/apply", { text: state.original, edits: edits });
      state.edits = edits;
      state.applied[key] = true;
      button.dataset.applied = "true";
      button.dataset.label = "Applied";
      input.value = state.prefix + out.text + state.suffix;
      scoreResult.hidden = true;
      updateMeta();
    });
  }

  async function runCoach() {
    var raw = input.value;
    var text = raw.trim();
    if (words(text) < 30) { showNotice("Use at least 30 words to find style patterns."); return; }
    await work(runBtn, "Reading…", async function () {
      var data = await postJSON("/api/coach", { text: text });
      if (state.baseline === null) state.baseline = text;
      state.original = text;
      state.prefix = raw.slice(0, raw.length - raw.trimStart().length);
      state.suffix = raw.slice(raw.trimEnd().length);
      state.edits = [];
      state.applied = {};
      render(data);
    });
  }

  function scoreLabel(report) {
    return report.overall_verdict === "Slop detected" ? "Very strong AI signals" : report.overall_verdict;
  }

  async function scoreText(button, compare) {
    var text = input.value.trim();
    if (words(text) < 30) { showNotice("Use at least 30 words before scoring."); return; }
    await work(button, "Scoring…", async function () {
      if (state.baseline === null) state.baseline = text;
      scoreResult.hidden = true;
      if (compare && state.baseline !== text && !state.baselineReport) {
        if (words(state.baseline) < 30) throw new Error("The original has fewer than 30 words and cannot be compared.");
        state.baselineReport = await postJSON("/api/analyze", { text: state.baseline });
      }
      var report = text === state.baseline && state.baselineReport
        ? state.baselineReport : await postJSON("/api/analyze", { text: text });
      if (text === state.baseline) state.baselineReport = report;
      var original = state.baselineReport;
      if (original && text !== state.baseline) {
        var delta = report.overall_score - original.overall_score;
        scoreVerdict.textContent = original.overall_score + " original → " + report.overall_score + " revised";
        scoreDetail.textContent = "Change: " + (delta > 0 ? "+" : "") + delta.toFixed(1) +
          " points. Revised result: " + scoreLabel(report) + ".";
      } else {
        scoreVerdict.textContent = report.overall_score + " / 100";
        scoreDetail.textContent = scoreLabel(report) + ". " + report.engines_flagged +
          " of " + report.engines_total + " engines flagged the text.";
      }
      scoreResult.hidden = false;
    });
  }

  function downloadDraft() {
    if (!input.value.trim()) return;
    var stem = state.filename ? state.filename.replace(/\.[^.]+$/, "") : "quillmark-draft";
    stem = stem.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").replace(/[. ]+$/, "") || "quillmark-draft";
    var link = document.createElement("a");
    var url = URL.createObjectURL(new Blob([input.value], { type: "text/plain;charset=utf-8" }));
    link.href = url;
    link.download = stem + "-revised.txt";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  input.addEventListener("input", function () {
    if (!input.value.trim()) {
      state.filename = "";
      state.baseline = null;
      state.baselineReport = null;
      sourceStatus.textContent = "No file loaded";
    }
    resetFindings();
    scoreResult.hidden = true;
    updateMeta();
    refreshControls();
  });
  upload.addEventListener("change", function () { void importFile(upload.files[0]); });
  downloadBtn.addEventListener("click", downloadDraft);
  runBtn.addEventListener("click", runCoach);
  scoreBtn.addEventListener("click", function () { void scoreText(scoreBtn, false); });
  rescoreBtn.addEventListener("click", function () { void scoreText(rescoreBtn, true); });
  copyBtn.addEventListener("click", async function () {
    try {
      await navigator.clipboard.writeText(input.value);
      copyBtn.textContent = "Copied";
      setTimeout(function () { copyBtn.textContent = "Copy edited text"; }, 1500);
    } catch (error) { showNotice("Clipboard access is unavailable. You can download the draft instead."); }
  });

  updateMeta();
  refreshControls();
})();
