import { calculateMetrics, progressClass } from "./analytics.js";
import { apiGet, apiPatch, apiPost } from "./api.js";
import { APP_CONFIG } from "./config.js";
import { draftWarnings, hasHighSeverityWarnings, renderDraftList } from "./questionDrafts.js";
import { exportProgress, getCourseState, getSettings, importProgress, resetAllProgress, updateSettings } from "./storage.js";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function warningText(warning) {
  if (typeof warning === "string") return warning;
  return warning?.message || warning?.code || "Validation warning";
}

export function buildAdminExportQuery(courseCode, formData) {
  const params = new URLSearchParams();
  params.set("include_lineage", formData.get("include_lineage") ? "true" : "false");
  params.set("include_review_metadata", formData.get("include_review_metadata") ? "true" : "false");
  params.set("include_retired", formData.get("include_retired") ? "true" : "false");
  return `/api/export/${encodeURIComponent(courseCode)}?${params.toString()}`;
}

export function retireQuestion(questionId, apiPostFn = apiPost) {
  return apiPostFn(`/api/questions/${encodeURIComponent(questionId)}/retire`, {});
}

export function restoreQuestion(questionId, apiPostFn = apiPost) {
  return apiPostFn(`/api/questions/${encodeURIComponent(questionId)}/restore`, {});
}

export function renderQuestionLineage(lineage = []) {
  if (!lineage.length) return `<p class="muted">No published lineage snapshot recorded.</p>`;
  return `
    <table class="data-table">
      <thead><tr><th>Source</th><th>Evidence</th><th>Reason</th></tr></thead>
      <tbody>
        ${lineage.map((row) => `
          <tr>
            <td>
              ${escapeHtml(row.source_title || "Unknown source")}
              <br><small>${escapeHtml(row.source_type || "")}</small>
              <div class="button-row">
                ${row.source_confidence ? `<span class="tag">${escapeHtml(row.source_confidence)}</span>` : ""}
                ${row.source_verification_status ? `<span class="tag">${escapeHtml(row.source_verification_status)}</span>` : ""}
              </div>
            </td>
            <td>${escapeHtml(row.evidence_text || "")}</td>
            <td><span class="tag blue">${escapeHtml(row.lineage_reason || "")}</span></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function progressBar(value) {
  return `<div class="progress ${progressClass(value)}" aria-label="${value}%"><span style="--value:${value}%"></span></div>`;
}

function tagList(items, color = "blue") {
  if (!items.length) return `<p class="muted">No items yet.</p>`;
  return `<ul class="pill-list">${items.map((item) => `<li class="tag ${color}">${item}</li>`).join("")}</ul>`;
}

function downloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function coursePackPayload(ctx) {
  return {
    exportedAt: new Date().toISOString(),
    app: APP_CONFIG,
    manifestEntry: ctx.bundle.course,
    course: ctx.bundle.meta,
    questions: ctx.bundle.questions,
    flashcards: ctx.bundle.flashcards,
    glossary: ctx.bundle.glossary,
    cheatsheets: ctx.bundle.cheatsheets,
    mockExams: ctx.bundle.mockExams,
    sources: ctx.bundle.sources
  };
}

export function renderDashboard(ctx) {
  const courseState = getCourseState(ctx.bundle.meta.id);
  const metrics = calculateMetrics(ctx.bundle, courseState);
  const recent = (courseState.sessions || []).slice(0, 8);
  const recommendedTopic = metrics.weakTopics[0]?.topic || metrics.highProbabilityTopics[0]?.topic || "";
  const latestMock = metrics.latestMock;

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Dashboard</h2>
        <p class="muted">${ctx.bundle.meta.description || ctx.bundle.meta.name}</p>
      </div>
      <div class="button-row">
        <button class="button button-primary" type="button" data-action="start-recommended" ${recommendedTopic ? "" : "disabled"}>Start Recommended Study</button>
        <button class="button" type="button" data-action="continue-study" ${metrics.recentQuestionId ? "" : "disabled"}>Continue Where I Left Off</button>
      </div>
    </div>

    <section class="grid grid-4" aria-label="Course summary">
      <article class="card"><span class="stat-value">${metrics.totalQuestions}</span><span class="stat-label">Questions loaded</span></article>
      <article class="card"><span class="stat-value">${metrics.accuracy}%</span><span class="stat-label">Overall accuracy</span></article>
      <article class="card"><span class="stat-value">${metrics.uniqueAnswered}</span><span class="stat-label">Unique answered</span></article>
      <article class="card">
        <span class="stat-value">${metrics.readiness}%</span>
        <span class="stat-label">OA readiness</span>
        ${progressBar(metrics.readiness)}
        <p class="helper-text">Weighted estimate: 40% overall accuracy, 30% high-probability accuracy, 20% mock average, 10% missed-question improvement.</p>
      </article>
    </section>

    <section class="grid grid-3" style="margin-top: 1rem;">
      <article class="card">
        <h3>Recommended Weak Topics</h3>
        ${tagList(metrics.weakTopics.map((topic) => `${topic.topic} (${topic.accuracy}%)`), "yellow")}
      </article>
      <article class="card">
        <h3>Next Actions</h3>
        ${tagList(metrics.recommendations, "green")}
      </article>
      <article class="card">
        <h3>Study Streak</h3>
        <span class="stat-value">${metrics.studyStreak}</span>
        <span class="stat-label">day streak</span>
        <p class="helper-text">Placeholder based on local study-session dates. Export progress before clearing browser data.</p>
      </article>
    </section>

    ${latestMock ? `
      <section class="card" style="margin-top: 1rem;">
        <div class="button-row" style="justify-content: space-between;">
          <div>
            <h3>Recent Mock Exam</h3>
            <p class="muted">${new Date(latestMock.date).toLocaleString()} - ${latestMock.correct}/${latestMock.total} correct</p>
          </div>
          <span class="tag ${latestMock.scorePct >= 70 ? "green" : "red"}">${latestMock.scorePct}%</span>
        </div>
      </section>
    ` : ""}

    <div class="section-title">
      <h3>Topic Progress</h3>
      <span class="muted">${metrics.missedCount} missed - ${metrics.bookmarkedCount} bookmarked</span>
    </div>
    <section class="grid grid-3">
      ${metrics.topicStats.map((topic) => `
        <article class="card topic-card">
          <header>
            <h4>${topic.topic}</h4>
            <span class="tag ${topic.highProbability ? "blue" : ""}">${topic.total} q</span>
          </header>
          ${progressBar(topic.accuracy)}
          <p class="muted">${topic.accuracy}% accuracy - ${topic.answered} attempts - ${topic.highProbability} high probability</p>
        </article>
      `).join("") || `
        <article class="empty-state">
          <h2>No topics yet.</h2>
          <p>Add course topics and questions to this course pack.</p>
        </article>
      `}
    </section>

    <section class="grid grid-2" style="margin-top: 1rem;">
      <article class="card">
        <h3>High Probability Topics</h3>
        <table class="data-table">
          <thead><tr><th>Topic</th><th>High probability questions</th><th>Accuracy</th></tr></thead>
          <tbody>
            ${metrics.highProbabilityTopics.map((topic) => `
              <tr><td>${topic.topic}</td><td>${topic.highProbability}</td><td>${topic.accuracy}%</td></tr>
            `).join("") || `<tr><td colspan="3">No high-probability topics are available.</td></tr>`}
          </tbody>
        </table>
      </article>
      <article class="card">
        <h3>Recent Session Stats</h3>
        ${recent.length ? `
          <table class="data-table">
            <thead><tr><th>Activity</th><th>Topic</th><th>Result</th></tr></thead>
            <tbody>
              ${recent.map((item) => `
                <tr>
                  <td>${item.type || "study"}</td>
                  <td>${item.topic || "All topics"}</td>
                  <td>${item.correct === true ? "Correct" : item.correct === false ? "Missed" : item.scorePct ? `${item.scorePct}%` : item.result || "Saved"}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<p class="muted">No study activity has been recorded yet. Start practice or flashcards to create a local history.</p>`}
      </article>
    </section>
  `;

  ctx.root.querySelector("[data-action='start-recommended']").addEventListener("click", () => {
    if (recommendedTopic) ctx.navigate("practice", { topic: recommendedTopic, probability: "4plus" });
  });
  ctx.root.querySelector("[data-action='continue-study']").addEventListener("click", () => {
    if (metrics.recentQuestionId) ctx.navigate("practice", { questionId: metrics.recentQuestionId });
  });
}

export function renderStudyGuide(ctx) {
  const query = (ctx.params.query || "").toLowerCase();
  const cheatsheets = ctx.bundle.cheatsheets || [];
  const glossary = ctx.bundle.glossary || [];

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Study Guide</h2>
        <p class="muted">High-yield cheat sheets, glossary terms, and source notes for ${ctx.bundle.meta.shortName}.</p>
      </div>
      <button class="button button-primary" type="button" data-action="study-mode">Study Questions</button>
    </div>

    <section class="card">
      <div class="filter-grid">
        <div class="field">
          <label for="guide-filter">Filter study guide</label>
          <input id="guide-filter" class="input" type="search" value="${ctx.params.query || ""}" placeholder="Search cheat sheets, terms, tips">
        </div>
      </div>
    </section>

    <div class="section-title"><h3>Cheat Sheets</h3><span class="muted">${cheatsheets.length} sheets</span></div>
    <section id="cheatsheet-list" class="grid grid-2">
      ${cheatsheets.length ? cheatsheets.map((sheet) => {
        const rows = Array.isArray(sheet.content) ? sheet.content : [];
        return `
          <article class="card guide-item" data-index="${[sheet.title, sheet.topic, JSON.stringify(sheet.content)].join(" ").toLowerCase()}">
            <div class="button-row" style="justify-content: space-between;">
              <h3>${sheet.title}</h3>
              <span class="tag blue">${sheet.topic}</span>
            </div>
            <table class="data-table">
              <tbody>
                ${rows.map((row) => `<tr><th>${row.label}</th><td>${row.value}</td></tr>`).join("")}
              </tbody>
            </table>
          </article>
        `;
      }).join("") : `
        <article class="empty-state">
          <h2>No cheat sheets yet.</h2>
          <p>Add high-yield sheets to <code>cheatsheets.json</code> for this course.</p>
        </article>
      `}
    </section>

    <div class="section-title"><h3>Glossary</h3><span class="muted">${glossary.length} terms</span></div>
    <section id="glossary-list" class="grid grid-3">
      ${glossary.length ? glossary.map((term) => `
        <article class="card guide-item" data-index="${[term.term, term.topic, term.definition, term.examTip, term.relatedTerms?.join(" ")].join(" ").toLowerCase()}">
          <span class="tag">${term.topic || "General"}</span>
          <h3>${term.term}</h3>
          <p>${term.definition}</p>
          ${term.examTip ? `<p class="muted"><strong>Exam tip:</strong> ${term.examTip}</p>` : ""}
          ${term.relatedTerms?.length ? tagList(term.relatedTerms) : ""}
        </article>
      `).join("") : `
        <article class="empty-state">
          <h2>No glossary terms yet.</h2>
          <p>Add terms to <code>glossary.json</code> for quick review.</p>
        </article>
      `}
    </section>
  `;

  const input = ctx.root.querySelector("#guide-filter");
  ctx.root.querySelector("[data-action='study-mode']").addEventListener("click", () => ctx.navigate("study"));
  const applyFilter = () => {
    const value = input.value.trim().toLowerCase();
    ctx.root.querySelectorAll(".guide-item").forEach((item) => {
      item.hidden = value && !item.dataset.index.includes(value);
    });
  };
  input.addEventListener("input", applyFilter);
  if (query) applyFilter();
}

export function renderAnalytics(ctx) {
  const courseState = getCourseState(ctx.bundle.meta.id);
  const metrics = calculateMetrics(ctx.bundle, courseState);
  const summary = {
    exportedAt: new Date().toISOString(),
    course: ctx.bundle.meta,
    overallAccuracy: metrics.accuracy,
    highProbabilityAccuracy: metrics.highProbabilityAccuracy,
    readiness: metrics.readiness,
    mockAverage: metrics.mockAverage,
    topicStats: metrics.topicStatsWeakest,
    mostMissedTopics: metrics.mostMissedTopics,
    mockHistory: metrics.mockHistory,
    recommendations: metrics.recommendations
  };

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Analytics</h2>
        <p class="muted">Progress is stored in this browser only.</p>
      </div>
      <button id="export-analytics" class="button button-primary" type="button">Export Analytics Summary</button>
    </div>

    <section class="grid grid-4">
      <article class="card"><span class="stat-value">${metrics.accuracy}%</span><span class="stat-label">Overall accuracy</span>${progressBar(metrics.accuracy)}</article>
      <article class="card"><span class="stat-value">${metrics.highProbabilityAccuracy}%</span><span class="stat-label">High-probability accuracy</span>${progressBar(metrics.highProbabilityAccuracy)}</article>
      <article class="card"><span class="stat-value">${metrics.mockAverage}%</span><span class="stat-label">Mock exam average</span>${progressBar(metrics.mockAverage)}</article>
      <article class="card"><span class="stat-value">${metrics.readiness}%</span><span class="stat-label">Readiness score</span>${progressBar(metrics.readiness)}</article>
    </section>

    <section class="grid grid-2" style="margin-top: 1rem;">
      <article class="card">
        <h3>Accuracy By Topic</h3>
        <table class="data-table">
          <thead><tr><th>Topic</th><th>Attempts</th><th>Missed</th><th>Accuracy</th></tr></thead>
          <tbody>
            ${metrics.topicStatsWeakest.map((topic) => `
              <tr>
                <td>${topic.topic}</td>
                <td>${topic.answered}</td>
                <td>${topic.missed}</td>
                <td>${topic.accuracy}%</td>
              </tr>
            `).join("") || `<tr><td colspan="4">No topic attempts have been recorded yet.</td></tr>`}
          </tbody>
        </table>
      </article>
      <article class="card">
        <h3>Most Missed Topics</h3>
        ${metrics.mostMissedTopics.length ? tagList(metrics.mostMissedTopics.map((topic) => `${topic.topic}: ${topic.missed} missed`), "red") : `<p class="muted">No missed-question history yet.</p>`}
      </article>
    </section>

    <section class="grid grid-2" style="margin-top: 1rem;">
      <article class="card">
        <h3>Mock Exam Trend</h3>
        ${metrics.mockHistory.length ? `
          <table class="data-table">
            <thead><tr><th>Date</th><th>Score</th><th>Questions</th><th>Estimate</th></tr></thead>
            <tbody>
              ${metrics.mockHistory.map((exam) => `
                <tr><td>${new Date(exam.date).toLocaleString()}</td><td>${exam.scorePct}%</td><td>${exam.correct}/${exam.total}</td><td>${exam.scorePct >= 70 ? "Pass range" : "Needs review"}</td></tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<p class="muted">No mock exams have been completed yet. Start a Mock OA to build a trend.</p>`}
      </article>
      <article class="card">
        <h3>Recommended Next Actions</h3>
        ${tagList(metrics.recommendations, "green")}
      </article>
    </section>
  `;

  ctx.root.querySelector("#export-analytics").addEventListener("click", () => {
    downloadJson(`studyforge-analytics-${ctx.bundle.meta.id}-${new Date().toISOString().slice(0, 10)}.json`, summary);
  });
}

export function renderSettings(ctx) {
  const settings = getSettings();
  const courseOptions = ctx.app.courses.map((course) => `
    <option value="${course.id}" ${settings.defaultCourse === course.id ? "selected" : ""}>${course.shortName || course.name}</option>
  `).join("");

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Settings</h2>
        <p class="muted">Manage device-local progress and StudyForge preferences.</p>
      </div>
    </div>

    <section class="grid grid-2">
      <article class="card">
        <h3>Preferences</h3>
        <label class="toggle-row">
          <span>Compact mode</span>
          <input id="setting-compact" type="checkbox" ${settings.compactMode ? "checked" : ""}>
        </label>
        <label class="toggle-row">
          <span>Show memory tricks by default</span>
          <input id="setting-memory" type="checkbox" ${settings.showMemoryDefault ? "checked" : ""}>
        </label>
        <label class="toggle-row">
          <span>Auto-next after correct practice answers</span>
          <input id="setting-autonext" type="checkbox" ${settings.autoNext ? "checked" : ""}>
        </label>
        <div class="field" style="margin-top: 1rem;">
          <label for="setting-default-course">Default course</label>
          <select id="setting-default-course" class="course-select">
            <option value="">First available course</option>
            ${courseOptions}
          </select>
        </div>
      </article>

      <article class="card">
        <h3>Progress Data</h3>
        <p class="muted">Progress is stored in localStorage under <code>${APP_CONFIG.storageKey}</code>.</p>
        <div class="button-row">
          <button id="export-progress" class="button button-primary" type="button">Export JSON</button>
          <label class="button" for="import-progress">Import JSON</label>
          <input id="import-progress" type="file" accept="application/json,.json" hidden>
          <button id="reset-all-progress" class="button button-danger" type="button">Reset All Progress</button>
        </div>
      </article>
    </section>

    <section class="grid grid-2" style="margin-top: 1rem;">
      <article class="card">
        <h3>Course Pack Portability</h3>
        <p class="muted">Export the active course as one JSON bundle for backup, editing, or sharing.</p>
        <div class="button-row">
          <button id="export-course-pack" class="button button-primary" type="button">Export Current Course Pack</button>
          <label class="button" for="import-course-pack">Import Course Pack</label>
          <input id="import-course-pack" type="file" accept="application/json,.json" hidden>
        </div>
        <p id="course-import-note" class="helper-text">Imported course packs can be inspected in the browser, but static apps cannot write files. Add new course packs manually under <code>data/</code> and register them in <code>data/courses.json</code> for permanent hosting.</p>
      </article>
      <article class="card">
        <h3>Keyboard Shortcuts</h3>
        <table class="data-table">
          <tbody>
            <tr><th>Practice/Study</th><td>1-4 select, Enter submits, N next, B bookmark</td></tr>
            <tr><th>Flashcards</th><td>Space flips, Right arrow next, 1 known, 2 missed</td></tr>
          </tbody>
        </table>
      </article>
    </section>
  `;

  const save = () => {
    const next = updateSettings({
      compactMode: ctx.root.querySelector("#setting-compact").checked,
      showMemoryDefault: ctx.root.querySelector("#setting-memory").checked,
      autoNext: ctx.root.querySelector("#setting-autonext").checked,
      defaultCourse: ctx.root.querySelector("#setting-default-course").value
    });
    document.body.classList.toggle("compact", next.compactMode);
    ctx.showStatus("Settings saved.");
  };

  ctx.root.querySelectorAll("input[type='checkbox'], select").forEach((control) => {
    control.addEventListener("change", save);
  });

  ctx.root.querySelector("#export-progress").addEventListener("click", () => {
    const blob = new Blob([exportProgress()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `studyforge-progress-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  ctx.root.querySelector("#import-progress").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      importProgress(await file.text());
      ctx.showStatus("Progress imported.");
      ctx.rerender();
    } catch (error) {
      ctx.showStatus(`Import failed: ${error.message}`);
    }
  });

  ctx.root.querySelector("#reset-all-progress").addEventListener("click", () => {
    if (confirm("Reset all StudyForge progress on this browser?")) {
      resetAllProgress();
      ctx.showStatus("All progress reset.");
      ctx.rerender();
    }
  });

  ctx.root.querySelector("#export-course-pack").addEventListener("click", () => {
    downloadJson(`studyforge-course-pack-${ctx.bundle.meta.id}.json`, coursePackPayload(ctx));
  });

  ctx.root.querySelector("#import-course-pack").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const imported = JSON.parse(await file.text());
      const name = imported.course?.name || imported.meta?.name || imported.name || file.name;
      ctx.root.querySelector("#course-import-note").textContent = `Loaded "${name}" for inspection only. To make it permanent, add its JSON files under data/ and register it in data/courses.json.`;
      ctx.showStatus("Course pack import preview loaded.");
    } catch (error) {
      ctx.showStatus(`Course pack import failed: ${error.message}`);
    }
  });
}

export function renderCourseBuilder(ctx) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Course Builder</h2>
        <p class="muted">A future workspace for turning source material into reusable StudyForge course packs.</p>
      </div>
      <button class="button" type="button" disabled>Coming Soon</button>
    </div>

    <section class="grid grid-3">
      ${[
        ["Import Source Files", "PDF, DOCX, TXT, and Markdown ingestion for source notes."],
        ["Generate Questions", "Draft OA-style questions with topics, difficulty, probability, and explanations."],
        ["Generate Flashcards", "Create front/back recall cards and memory prompts."],
        ["Generate Glossary", "Extract terms, definitions, related concepts, and exam tips."],
        ["Generate Cheat Sheets", "Build high-yield comparison tables and cram sheets."],
        ["Generate Mock Exam", "Assemble balanced mock exams from a course question bank."]
      ].map(([title, copy]) => `
        <article class="card">
          <span class="tag blue">Planned</span>
          <h3>${title}</h3>
          <p class="muted">${copy}</p>
        </article>
      `).join("")}
    </section>

    <section class="card" style="margin-top: 1rem;">
      <h3>Static App Limitation</h3>
      <p class="muted">StudyForge can import and export JSON in the browser, but it cannot write new files to <code>data/</code>. Permanent courses should be added as folders in the repository and registered in <code>data/courses.json</code>.</p>
    </section>
  `;
}

export async function handleAdminCreateUserSubmit(event, options = {}) {
  event?.preventDefault?.();

  const {
    apiPostFn = apiPost,
    formDataFactory = (form) => new FormData(form),
    renderUsers = async () => {},
    showStatus = () => {}
  } = options;
  const form = event?.currentTarget || null;

  if (!form) {
    showStatus("User create failed: form is unavailable.");
    return;
  }

  const data = formDataFactory(form);

  try {
    await apiPostFn("/api/users", {
      username: String(data.get("username") || ""),
      display_name: String(data.get("display_name") || ""),
      password: String(data.get("password") || ""),
      role: String(data.get("role") || "student")
    });
    if (typeof form.reset === "function") {
      form.reset();
    }
    showStatus("User created.");
    await renderUsers();
  } catch (error) {
    showStatus(`User create failed: ${error.message}`);
  }
}

export function renderAdmin(ctx) {
  if (!ctx?.root) return;

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Administration</h2>
        <p class="muted">Manage local users, database status, and course import/export.</p>
      </div>
      <button id="admin-refresh" class="button" type="button">Refresh</button>
    </div>

    <section class="grid grid-2">
      <article class="card">
        <h3>Backend Status</h3>
        <div id="admin-health" class="admin-panel"><p class="muted">Loading status...</p></div>
      </article>
      <article class="card">
        <h3>Course Import / Export</h3>
        <p class="muted">Import a static course from a server path or export the DB course back to a static-compatible bundle.</p>
        <div class="field">
          <label for="admin-import-path">Server import path</label>
          <input id="admin-import-path" class="input" value="../data/${ctx.bundle.meta.id}">
        </div>
        <div class="button-row">
          <button id="admin-import-course" class="button button-primary" type="button">Import Static Course</button>
          <button id="admin-export-course" class="button" type="button">Export Active DB Course</button>
        </div>
        <form id="admin-export-options" class="grid grid-3" style="margin-top: 0.75rem;">
          <label class="toggle-row" style="border-bottom: 0; padding-bottom: 0;">
            <span>Include lineage</span>
            <input name="include_lineage" type="checkbox" checked>
          </label>
          <label class="toggle-row" style="border-bottom: 0; padding-bottom: 0;">
            <span>Review metadata</span>
            <input name="include_review_metadata" type="checkbox" checked>
          </label>
          <label class="toggle-row" style="border-bottom: 0; padding-bottom: 0;">
            <span>Retired questions</span>
            <input name="include_retired" type="checkbox">
          </label>
        </form>
        <div id="admin-import-result" class="helper-text"></div>
        <div id="admin-export-validation"></div>
      </article>
    </section>

    <section class="grid grid-2" style="margin-top: 1rem;">
      <article class="card">
        <h3>Create User</h3>
        <form id="admin-create-user" class="grid">
          <div class="field">
            <label for="admin-username">Username</label>
            <input id="admin-username" class="input" name="username" required>
          </div>
          <div class="field">
            <label for="admin-display-name">Display name</label>
            <input id="admin-display-name" class="input" name="display_name" required>
          </div>
          <div class="field">
            <label for="admin-password">Temporary password</label>
            <input id="admin-password" class="input" name="password" type="password" required minlength="6">
          </div>
          <div class="field">
            <label for="admin-role">Role</label>
            <select id="admin-role" class="course-select" name="role">
              <option value="student">student</option>
              <option value="instructor">instructor</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <button class="button button-primary" type="submit">Create User</button>
        </form>
      </article>
      <article class="card">
        <h3>Users</h3>
        <div id="admin-users"><p class="muted">Loading users...</p></div>
      </article>
    </section>

    <section class="grid grid-2" style="margin-top: 1rem;">
      <article class="card">
        <h3>Question Review</h3>
        <div id="admin-question-counts"><p class="muted">Loading question status counts...</p></div>
        <div class="button-row" style="margin-top: 0.75rem;">
          <button id="admin-load-generated" class="button" type="button">Generated</button>
          <button id="admin-load-drafts" class="button" type="button">Question Drafts</button>
          <button id="admin-load-drafts-needs-review" class="button" type="button">Needs Review</button>
          <button id="admin-load-drafts-warnings" class="button" type="button">Has Warnings</button>
          <button id="admin-load-drafts-ready" class="button" type="button">Ready to Verify</button>
          <button id="admin-load-drafts-rejected" class="button" type="button">Rejected</button>
          <button id="admin-load-drafts-published" class="button" type="button">Published</button>
          <button id="admin-load-low-confidence" class="button" type="button">Low Confidence</button>
          <button id="admin-load-warnings" class="button" type="button">Validation Warnings</button>
        </div>
      </article>
      <article class="card">
        <h3>Review Queue</h3>
        <div id="admin-review-list"><p class="muted">Choose a review queue.</p></div>
      </article>
    </section>
  `;

  const renderHealth = async () => {
    const [health, stats] = await Promise.all([
      apiGet("/api/admin/health"),
      apiGet("/api/admin/db-stats")
    ]);
    const healthPanel = ctx.root.querySelector("#admin-health");
    if (!healthPanel) return;
    healthPanel.innerHTML = `
      <table class="data-table">
        <tbody>
          <tr><th>Service</th><td>${health.service}</td></tr>
          <tr><th>Users</th><td>${stats.users}</td></tr>
          <tr><th>Courses</th><td>${stats.courses}</td></tr>
          <tr><th>Questions</th><td>${stats.questions}</td></tr>
          <tr><th>Attempts</th><td>${stats.attempts}</td></tr>
        </tbody>
      </table>
    `;
  };

  const renderUsers = async () => {
    const users = await apiGet("/api/users");
    const usersPanel = ctx.root.querySelector("#admin-users");
    if (!usersPanel) return;
    usersPanel.innerHTML = `
      <table class="data-table">
        <thead><tr><th>User</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          ${users.map((user) => `
            <tr data-user-id="${user.id}">
              <td>${user.display_name}<br><small>${user.username}</small></td>
              <td>
                <select class="course-select admin-role-select" data-user-role="${user.id}">
                  ${["admin", "instructor", "student"].map((role) => `<option value="${role}" ${user.role === role ? "selected" : ""}>${role}</option>`).join("")}
                </select>
              </td>
              <td>${user.is_active ? "Active" : "Disabled"}</td>
              <td>
                <div class="button-row">
                  <button class="button" data-user-toggle="${user.id}" data-next-active="${!user.is_active}" type="button">${user.is_active ? "Disable" : "Enable"}</button>
                  <button class="button" data-user-reset="${user.id}" type="button">Reset Password</button>
                </div>
              </td>
            </tr>
          `).join("") || `<tr><td colspan="4">No users.</td></tr>`}
        </tbody>
      </table>
    `;

    ctx.root.querySelectorAll("[data-user-role]").forEach((select) => {
      select.addEventListener("change", async () => {
        try {
          await apiPatch(`/api/users/${select.dataset.userRole}`, { role: select.value });
          ctx.showStatus("User role updated.");
          await renderUsers();
        } catch (error) {
          ctx.showStatus(`Role update failed: ${error.message}`);
        }
      });
    });
    ctx.root.querySelectorAll("[data-user-toggle]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await apiPatch(`/api/users/${button.dataset.userToggle}`, { is_active: button.dataset.nextActive === "true" });
          ctx.showStatus("User status updated.");
          await renderUsers();
        } catch (error) {
          ctx.showStatus(`User status update failed: ${error.message}`);
        }
      });
    });
    ctx.root.querySelectorAll("[data-user-reset]").forEach((button) => {
      button.addEventListener("click", async () => {
        const password = prompt("Temporary password (minimum 6 characters)");
        if (!password) return;
        try {
          await apiPost(`/api/users/${button.dataset.userReset}/reset-password`, { password });
          ctx.showStatus("Password reset.");
        } catch (error) {
          ctx.showStatus(`Password reset failed: ${error.message}`);
        }
      });
    });
  };

  const renderQuestionCounts = async () => {
    const counts = await apiGet("/api/questions/status-counts");
    const countsPanel = ctx.root.querySelector("#admin-question-counts");
    if (!countsPanel) return;
    countsPanel.innerHTML = `
      <div class="button-row">
        ${["generated", "reviewed", "verified", "retired"].map((status) => `<span class="tag ${status === "verified" ? "green" : status === "retired" ? "red" : status === "reviewed" ? "blue" : "yellow"}">${status}: ${counts[status] || 0}</span>`).join("")}
      </div>
    `;
  };

  const renderReviewList = (items) => {
    const reviewList = ctx.root.querySelector("#admin-review-list");
    if (!reviewList) return;
    reviewList.innerHTML = items.length ? `
      <div class="admin-review-list">
        ${items.slice(0, 15).map((question) => `
          <article class="review-item" data-review-question="${question.id}">
            <div class="button-row">
              <span class="tag blue">${question.topic || "General"}</span>
              <span class="tag">${question.status || "generated"}</span>
              <span class="tag yellow">Confidence ${question.confidence || "?"}</span>
            </div>
            <h4>${question.id}</h4>
            <p>${question.question}</p>
            ${question.warnings?.length ? `<ul class="warning-list">${question.warnings.map((warning) => `<li>${escapeHtml(warningText(warning))}</li>`).join("")}</ul>` : ""}
            <div class="button-row">
              <button class="button" data-status-target="${question.id}" data-status-value="generated" type="button">Generated</button>
              <button class="button" data-status-target="${question.id}" data-status-value="review" type="button">Reviewed</button>
              <button class="button button-success" data-status-target="${question.id}" data-status-value="verify" type="button">Verified</button>
              ${question.status === "retired"
                ? `<button class="button button-success" data-question-restore="${question.id}" type="button">Restore</button>`
                : `<button class="button button-danger" data-question-retire="${question.id}" type="button">Retire</button>`}
              <button class="button" data-question-lineage="${question.id}" type="button">Lineage</button>
            </div>
            <div data-question-lineage-panel="${question.id}"></div>
          </article>
        `).join("")}
      </div>
    ` : `<p class="muted">No questions in this queue.</p>`;

    ctx.root.querySelectorAll("[data-status-target]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await apiPost(`/api/questions/${encodeURIComponent(button.dataset.statusTarget)}/${button.dataset.statusValue}`, {});
          ctx.showStatus("Question status updated.");
          await renderQuestionCounts();
          button.closest(".review-item")?.remove();
        } catch (error) {
          ctx.showStatus(`Question status update failed: ${error.message}`);
        }
      });
    });
    ctx.root.querySelectorAll("[data-question-retire]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await retireQuestion(button.dataset.questionRetire);
          ctx.showStatus("Question retired.");
          await renderQuestionCounts();
          button.closest(".review-item")?.remove();
        } catch (error) {
          ctx.showStatus(`Question retire failed: ${error.message}`);
        }
      });
    });
    ctx.root.querySelectorAll("[data-question-restore]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await restoreQuestion(button.dataset.questionRestore);
          ctx.showStatus("Question restored.");
          await renderQuestionCounts();
          button.closest(".review-item")?.remove();
        } catch (error) {
          ctx.showStatus(`Question restore failed: ${error.message}`);
        }
      });
    });
    ctx.root.querySelectorAll("[data-question-lineage]").forEach((button) => {
      button.addEventListener("click", async () => {
        const panel = ctx.root.querySelector(`[data-question-lineage-panel="${button.dataset.questionLineage}"]`);
        if (!panel) return;
        try {
          panel.innerHTML = renderQuestionLineage(await apiGet(`/api/questions/${encodeURIComponent(button.dataset.questionLineage)}/lineage`));
        } catch (error) {
          ctx.showStatus(`Question lineage failed: ${error.message}`);
        }
      });
    });
  };

  const loadReviewQueue = async (path) => {
    try {
      renderReviewList(await apiGet(path));
    } catch (error) {
      ctx.showStatus(`Review queue failed: ${error.message}`);
    }
  };

  const draftQueueFilters = {
    all: (draft) => draft.status !== "published",
    needsReview: (draft) => draft.status === "needs_review",
    warnings: (draft) => draftWarnings(draft).length > 0,
    ready: (draft) => draft.status === "reviewed" && !hasHighSeverityWarnings(draft),
    rejected: (draft) => draft.status === "rejected",
    published: (draft) => draft.status === "published"
  };

  const loadDraftReviewQueue = async (filterName = "all") => {
    try {
      const reviewList = ctx.root.querySelector("#admin-review-list");
      if (!reviewList) return;
      const drafts = await apiGet("/api/question-drafts?include_rejected=true");
      const filter = draftQueueFilters[filterName] || draftQueueFilters.all;
      reviewList.innerHTML = renderDraftList(drafts.filter(filter));
      reviewList.querySelectorAll("[data-draft-open]").forEach((button) => {
        button.addEventListener("click", () => ctx.navigate("questionDrafts", { draftId: button.dataset.draftOpen }));
      });
    } catch (error) {
      ctx.showStatus(`Question draft queue failed: ${error.message}`);
    }
  };

  const refresh = async () => {
    try {
      await Promise.all([renderHealth(), renderUsers(), renderQuestionCounts()]);
    } catch (error) {
      ctx.showStatus(`Admin refresh failed: ${error.message}`);
    }
  };

  ctx.root.querySelector("#admin-refresh")?.addEventListener("click", refresh);
  ctx.root.querySelector("#admin-load-generated")?.addEventListener("click", () => loadReviewQueue("/api/questions?status=generated"));
  ctx.root.querySelector("#admin-load-drafts")?.addEventListener("click", () => loadDraftReviewQueue("all"));
  ctx.root.querySelector("#admin-load-drafts-needs-review")?.addEventListener("click", () => loadDraftReviewQueue("needsReview"));
  ctx.root.querySelector("#admin-load-drafts-warnings")?.addEventListener("click", () => loadDraftReviewQueue("warnings"));
  ctx.root.querySelector("#admin-load-drafts-ready")?.addEventListener("click", () => loadDraftReviewQueue("ready"));
  ctx.root.querySelector("#admin-load-drafts-rejected")?.addEventListener("click", () => loadDraftReviewQueue("rejected"));
  ctx.root.querySelector("#admin-load-drafts-published")?.addEventListener("click", () => loadDraftReviewQueue("published"));
  ctx.root.querySelector("#admin-load-low-confidence")?.addEventListener("click", () => loadReviewQueue("/api/questions/low-confidence?threshold=6"));
  ctx.root.querySelector("#admin-load-warnings")?.addEventListener("click", () => loadReviewQueue("/api/questions/validation-warnings"));
  ctx.root.querySelector("#admin-create-user")?.addEventListener("submit", (event) => {
    handleAdminCreateUserSubmit(event, {
      renderUsers,
      showStatus: ctx.showStatus
    });
  });
  ctx.root.querySelector("#admin-import-course")?.addEventListener("click", async () => {
    try {
      const importPath = ctx.root.querySelector("#admin-import-path")?.value?.trim() || "";
      const result = await apiPost(`/api/import/legacy-static-course/${ctx.bundle.meta.id}`, importPath ? { path: importPath } : {});
      const importResult = ctx.root.querySelector("#admin-import-result");
      if (importResult) {
        importResult.textContent = `Imported ${result.result.course_code}: ${result.result.questions} questions, ${result.result.flashcards} flashcards, ${result.result.glossary || 0} glossary terms.`;
      }
      ctx.showStatus(`Imported ${result.result.course_code}.`);
      await refresh();
    } catch (error) {
      ctx.showStatus(`Import failed: ${error.message}`);
    }
  });
  ctx.root.querySelector("#admin-export-course")?.addEventListener("click", async () => {
    try {
      const validation = await apiGet(`/api/export/${encodeURIComponent(ctx.bundle.meta.id)}/validate`);
      const validationPanel = ctx.root.querySelector("#admin-export-validation");
      if (validationPanel) {
        validationPanel.innerHTML = validation.warnings?.length
          ? `<div class="warning-list" style="margin-top: 0.75rem;"><strong>Export warnings</strong><ul>${validation.warnings.map((warning) => `<li><code>${escapeHtml(warning.code)}</code> ${escapeHtml(warning.message)}</li>`).join("")}</ul></div>`
          : `<p class="helper-text">Export validation passed.</p>`;
      }
      const optionsForm = ctx.root.querySelector("#admin-export-options");
      const query = buildAdminExportQuery(ctx.bundle.meta.id, new FormData(optionsForm));
      const exported = await apiGet(query);
      downloadJson(`studyforge-db-export-${ctx.bundle.meta.id}.json`, exported);
    } catch (error) {
      ctx.showStatus(`Export failed: ${error.message}`);
    }
  });

  refresh();
}
