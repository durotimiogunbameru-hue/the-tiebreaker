/* The Tiebreaker — frontend logic
   Builds the dynamic form, calls POST /api/analyze, and renders the SWOT
   matrices and weighted priority ranking. No framework, no build step. */

(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  const optionsList = $("#options-list");
  const criteriaList = $("#criteria-list");
  const form = $("#decision-form");
  const results = $("#results");
  const formError = $("#form-error");
  const analyzeBtn = $("#analyze-btn");
  const engineBadge = $("#engine-badge");

  // ---------- Dynamic option rows ----------
  function addOption(value = "") {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <input type="text" class="option-input" maxlength="120"
             placeholder="Name an option…" />
      <button type="button" class="icon-btn remove" title="Remove">×</button>`;
    row.querySelector(".option-input").value = value;
    row.querySelector(".remove").addEventListener("click", () => {
      if (optionsList.children.length > 2) row.remove();
    });
    optionsList.appendChild(row);
  }

  // ---------- Dynamic criterion rows ----------
  function addCriterion(name = "", weight = 3) {
    const row = document.createElement("div");
    row.className = "criterion-row";
    row.innerHTML = `
      <input type="text" class="criterion-input" maxlength="80"
             placeholder="What matters? e.g. Cost, Growth, Risk…" />
      <div class="weight-cell">
        <input type="range" class="weight-input" min="1" max="5" step="1" />
        <span class="weight-val"></span>
      </div>
      <button type="button" class="icon-btn remove" title="Remove">×</button>`;
    const nameEl = row.querySelector(".criterion-input");
    const rangeEl = row.querySelector(".weight-input");
    const valEl = row.querySelector(".weight-val");
    nameEl.value = name;
    rangeEl.value = weight;
    valEl.textContent = weight;
    rangeEl.addEventListener("input", () => (valEl.textContent = rangeEl.value));
    row.querySelector(".remove").addEventListener("click", () => row.remove());
    criteriaList.appendChild(row);
  }

  // ---------- Collect form values ----------
  function collect() {
    const question = $("#question").value.trim();
    const options = [...document.querySelectorAll(".option-input")]
      .map((el) => el.value.trim())
      .filter(Boolean);
    const criteria = [...document.querySelectorAll(".criterion-row")]
      .map((row) => ({
        name: row.querySelector(".criterion-input").value.trim(),
        weight: Number(row.querySelector(".weight-input").value),
      }))
      .filter((c) => c.name);
    return { question, options, criteria };
  }

  function validate({ question, options }) {
    if (question.length < 3) return "Describe the decision you're weighing.";
    if (options.length < 2) return "Give at least two options to compare.";
    const lowered = options.map((o) => o.toLowerCase());
    if (new Set(lowered).size !== lowered.length) return "Options must be distinct.";
    return null;
  }

  // ---------- Submit ----------
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    formError.textContent = "";
    const data = collect();
    const err = validate(data);
    if (err) {
      formError.textContent = err;
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: data.question,
          options: data.options,
          criteria: data.criteria.length ? data.criteria : null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(detailToText(body.detail) || `Request failed (${res.status})`);
      }
      render(await res.json());
    } catch (ex) {
      formError.textContent = ex.message || "Something went wrong.";
      results.classList.add("hidden");
    } finally {
      setLoading(false);
    }
  });

  function detailToText(detail) {
    if (!detail) return "";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg || "").join("; ");
    return "";
  }

  function setLoading(on) {
    analyzeBtn.disabled = on;
    analyzeBtn.querySelector(".btn-label").innerHTML = on
      ? '<span class="spinner"></span>Analyzing…'
      : "Break the tie";
  }

  // ---------- Render results ----------
  function render(data) {
    engineBadge.textContent = data.engine === "claude" ? "Analyzed by Claude" : "Demo mode (mock)";
    engineBadge.className = "badge " + data.engine;

    const rec = data.recommendation || {};
    const conf = (rec.confidence || "medium").toLowerCase();

    const html = [];

    // Verdict
    html.push(`
      <div class="verdict">
        <div class="verdict-eyebrow">The verdict</div>
        <h2>Lean toward <span class="winner-name">${esc(rec.winner || "—")}</span>
          <span class="confidence-tag ${conf}">${conf} confidence</span>
        </h2>
        <p>${esc(rec.rationale || "")}</p>
      </div>`);

    // Priority ranking
    const maxTotal = Math.max(...data.results.map((r) => r.weighted_total), 10);
    html.push(`<div>
      <h2 class="section-title">Weighted priority ranking</h2>
      <p class="section-sub">Each option scored 0–10 per criterion, weighted by how much it matters to you.</p>
      <div class="ranking">
        ${data.results.map((r, i) => rankCard(r, i, data.criteria, maxTotal)).join("")}
      </div>
    </div>`);

    // SWOT
    html.push(`<div>
      <h2 class="section-title">SWOT analysis</h2>
      <p class="section-sub">Strengths &amp; Weaknesses are internal; Opportunities &amp; Threats are external.</p>
      <div class="swot-grid">
        ${data.results.map(swotCard).join("")}
      </div>
    </div>`);

    if (data.warnings && data.warnings.length) {
      html.push(`<div class="warnings">${data.warnings.map(esc).join("<br>")}</div>`);
    }

    results.innerHTML = html.join("");
    results.classList.remove("hidden");
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function rankCard(r, i, criteria, maxTotal) {
    const bars = criteria
      .map((c) => {
        const score = r.scores[c.name] ?? 5;
        const pct = (score / 10) * 100;
        return `
          <div class="bar-row" title="${esc(r.reasons[c.name] || "")}">
            <span class="bar-label">${esc(c.name)}</span>
            <span class="bar-track"><span class="bar-fill" style="width:${pct}%"></span></span>
            <span class="bar-score">${score}</span>
          </div>`;
      })
      .join("");
    return `
      <div class="rank-card ${i === 0 ? "leader" : ""}">
        <div class="rank-head">
          <div><span class="rank-pos">#${i + 1}</span><span class="rank-name">${esc(r.name)}</span></div>
          <div class="rank-total">${r.weighted_total.toFixed(1)}<small> / 10</small></div>
        </div>
        ${bars}
      </div>`;
  }

  function swotCard(r) {
    const quad = (cls, title, items) => `
      <div class="quad ${cls}">
        <h4>${title}</h4>
        ${
          items && items.length
            ? `<ul>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`
            : `<span class="empty">—</span>`
        }
      </div>`;
    const s = r.swot || {};
    return `
      <div class="swot-card">
        <h3>${esc(r.name)}</h3>
        <div class="swot-quads">
          ${quad("s", "Strengths", s.strengths)}
          ${quad("w", "Weaknesses", s.weaknesses)}
          ${quad("o", "Opportunities", s.opportunities)}
          ${quad("t", "Threats", s.threats)}
        </div>
      </div>`;
  }

  function esc(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // ---------- Example loader ----------
  function loadExample() {
    $("#question").value =
      "Should I take the early-stage startup offer or stay in my stable corporate role?";
    optionsList.innerHTML = "";
    addOption("Join the startup");
    addOption("Stay at current job");
    criteriaList.innerHTML = "";
    addCriterion("Compensation", 4);
    addCriterion("Long-term growth", 5);
    addCriterion("Job security", 3);
    addCriterion("Day-to-day enjoyment", 4);
    addCriterion("Work-life balance", 3);
    formError.textContent = "";
  }

  // ---------- Health check for the engine badge ----------
  async function pingEngine() {
    try {
      const res = await fetch("/api/health");
      const { engine } = await res.json();
      engineBadge.textContent = engine === "claude" ? "Claude connected" : "Demo mode (mock)";
      engineBadge.className = "badge " + engine;
    } catch {
      engineBadge.textContent = "";
    }
  }

  // ---------- Init ----------
  $("#add-option").addEventListener("click", () => addOption());
  $("#add-criterion").addEventListener("click", () => addCriterion());
  $("#example-btn").addEventListener("click", loadExample);

  addOption();
  addOption();
  addCriterion("Overall upside", 4);
  addCriterion("Cost / effort", 3);
  addCriterion("Risk", 3);
  pingEngine();
})();
