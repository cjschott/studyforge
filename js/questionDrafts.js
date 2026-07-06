import { apiGet, apiPost, apiPut, isBackendMode } from "./api.js";


const STATUS_VALUES = ["generated", "needs_review", "reviewed", "verified", "rejected", "published"];
const CONFIDENCE_VALUES = ["generated", "reviewed", "verified", "unverified"];


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function optionList(values, selected = "") {
  return values.map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`).join("");
}


function normalizeFilter(value) {
  return String(value ?? "").trim().toLowerCase();
}


function formatJson(value) {
  return JSON.stringify(value ?? [], null, 2);
}


function parseJsonField(value, fallback) {
  const text = String(value ?? "").trim();
  if (!text) return fallback;
  return JSON.parse(text);
}


export function draftStatusClass(status) {
  if (status === "published" || status === "verified") return "green";
  if (status === "reviewed") return "blue";
  if (status === "rejected") return "red";
  return "yellow";
}


export function normalizeDraftWarning(warning) {
  if (typeof warning === "string") {
    return { code: warning, severity: "medium", message: warning };
  }
  const severity = ["low", "medium", "high"].includes(warning?.severity) ? warning.severity : "medium";
  return {
    code: String(warning?.code || "validation_warning"),
    severity,
    message: String(warning?.message || warning?.code || "Validation warning")
  };
}


export function draftWarnings(draft) {
  return (draft?.warnings || []).map(normalizeDraftWarning);
}


export function hasHighSeverityWarnings(draft) {
  return draftWarnings(draft).some((warning) => warning.severity === "high");
}


export function isReadyToPublish(draft) {
  return ["reviewed", "verified"].includes(draft?.status) && !hasHighSeverityWarnings(draft);
}


function warningTagClass(severity) {
  if (severity === "high") return "red";
  if (severity === "low") return "blue";
  return "yellow";
}


function warningSearchText(warnings = []) {
  return warnings
    .map(normalizeDraftWarning)
    .map((warning) => `${warning.code} ${warning.severity} ${warning.message}`)
    .join(" ");
}


export function filterDrafts(drafts, filters = {}) {
  const status = normalizeFilter(filters.status);
  const courseCode = normalizeFilter(filters.courseCode);
  const conceptId = normalizeFilter(filters.conceptId);
  const search = normalizeFilter(filters.search);
  const includeRejected = Boolean(filters.includeRejected);
  const warningsOnly = Boolean(filters.warningsOnly);
  const highSeverityOnly = Boolean(filters.highSeverityOnly);

  return drafts.filter((draft) => {
    if (!includeRejected && draft.status === "rejected") return false;
    if (status && draft.status !== status) return false;
    if (courseCode && normalizeFilter(draft.course_code) !== courseCode) return false;
    if (conceptId && String(draft.concept_id || "") !== conceptId) return false;
    if (warningsOnly && !draftWarnings(draft).length) return false;
    if (highSeverityOnly && !hasHighSeverityWarnings(draft)) return false;
    if (!search) return true;
    const haystack = normalizeFilter(`${draft.stem} ${draft.explanation || ""} ${formatJson(draft.choices)} ${draft.concept_name || ""} ${draft.source_title || ""} ${warningSearchText(draft.warnings)}`);
    return haystack.includes(search);
  });
}


function warningTags(warnings = []) {
  const normalized = warnings.map(normalizeDraftWarning);
  return normalized.length
    ? normalized.map((warning) => `<span class="tag ${warningTagClass(warning.severity)}" title="${escapeHtml(warning.message)}">${escapeHtml(warning.code)}</span>`).join("")
    : `<span class="tag green">no warnings</span>`;
}


function warningCountLabel(warnings = []) {
  const count = warnings.length;
  return `${count} ${count === 1 ? "warning" : "warnings"}`;
}


function renderWarningGroups(warnings = []) {
  const normalized = warnings.map(normalizeDraftWarning);
  if (!normalized.length) return `<div class="button-row"><span class="tag green">no warnings</span></div>`;
  return ["high", "medium", "low"]
    .map((severity) => {
      const items = normalized.filter((warning) => warning.severity === severity);
      if (!items.length) return "";
      return `
        <div class="warning-list" style="margin-top: 0.75rem;">
          <strong>${severity} severity</strong>
          <ul>
            ${items.map((warning) => `<li><code>${escapeHtml(warning.code)}</code> ${escapeHtml(warning.message)}</li>`).join("")}
          </ul>
        </div>
      `;
    })
    .join("");
}


function renderPublishHistory(history = []) {
  if (!history.length) return `<p class="muted">No publish history recorded.</p>`;
  return `
    <table class="data-table">
      <thead><tr><th>Action</th><th>Status</th><th>When</th></tr></thead>
      <tbody>
        ${history.map((row) => `
          <tr>
            <td><span class="tag blue">${escapeHtml(row.action)}</span></td>
            <td>${escapeHtml(row.previous_status || "none")} -> ${escapeHtml(row.new_status || "")}</td>
            <td>${escapeHtml(row.created_at || "")}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}


function listFromValue(value) {
  if (Array.isArray(value)) return value.map((item) => String(item));
  if (value && typeof value === "object") return Object.values(value).map((item) => String(item));
  return [];
}


function answerSet(value) {
  if (Array.isArray(value)) return new Set(value.map((item) => String(item).trim().toLowerCase()));
  if (value && typeof value === "object") return new Set(Object.values(value).map((item) => String(item).trim().toLowerCase()));
  const text = String(value ?? "").trim().toLowerCase();
  return text ? new Set([text]) : new Set();
}


function renderStructuredExplanationEditor(draft) {
  const explanationJson = draft.explanation_json && typeof draft.explanation_json === "object" ? draft.explanation_json : {};
  const incorrect = explanationJson.incorrect && typeof explanationJson.incorrect === "object" ? explanationJson.incorrect : {};
  const answers = answerSet(draft.correct_answer);
  const choices = listFromValue(draft.choices);
  const wrongChoices = choices.filter((choice, index) => {
    const letter = String.fromCharCode(65 + index).toLowerCase();
    return !answers.has(choice.trim().toLowerCase()) && !answers.has(letter);
  });
  return `
    <div class="field">
      <label for="draft-explanation-correct">Why correct answer is correct</label>
      <textarea id="draft-explanation-correct" class="textarea" name="explanation_correct">${escapeHtml(explanationJson.correct || "")}</textarea>
    </div>
    ${wrongChoices.map((choice, index) => {
      const fieldId = `draft-explanation-wrong-${index}`;
      return `
        <div class="field">
          <label for="${fieldId}">Why ${escapeHtml(choice)} is wrong</label>
          <textarea id="${fieldId}" class="textarea" name="explanation_incorrect::${escapeHtml(choice)}">${escapeHtml(incorrect[choice] || "")}</textarea>
        </div>
      `;
    }).join("")}
  `;
}


export function buildDraftPayloadFromFormData(formData) {
  const incorrect = {};
  for (const [key, value] of formData.entries()) {
    if (!String(key).startsWith("explanation_incorrect::")) continue;
    const choice = String(key).slice("explanation_incorrect::".length);
    const reason = String(value || "").trim();
    if (choice && reason) incorrect[choice] = reason;
  }
  return {
    course_code: String(formData.get("course_code") || ""),
    question_type: String(formData.get("question_type") || "single_choice"),
    stem: String(formData.get("stem") || ""),
    choices: parseJsonField(formData.get("choices"), []),
    correct_answer: parseJsonField(formData.get("correct_answer"), []),
    explanation: String(formData.get("explanation") || ""),
    explanation_json: {
      correct: String(formData.get("explanation_correct") || "").trim(),
      incorrect
    },
    difficulty: Number(formData.get("difficulty") || 3),
    oa_probability: Number(formData.get("oa_probability") || 3),
    status: String(formData.get("status") || "needs_review"),
    confidence: String(formData.get("confidence") || "generated")
  };
}


export function renderDraftList(drafts) {
  if (!drafts.length) return `<p class="muted">No question drafts match the current filters.</p>`;
  return `
    <table class="data-table">
      <thead><tr><th>Draft</th><th>Status</th><th>Lineage</th><th>Warnings</th><th>Actions</th></tr></thead>
      <tbody>
        ${drafts.map((draft) => `
          <tr>
            <td>
              <strong>${escapeHtml(draft.stem)}</strong>
              <br><small>${escapeHtml(draft.course_code)} · ${escapeHtml(draft.question_type || "single_choice")}</small>
            </td>
            <td>
              <span class="tag ${draftStatusClass(draft.status)}">${escapeHtml(draft.status)}</span>
              <span class="tag">${escapeHtml(draft.confidence)}</span>
              <span class="tag ${isReadyToPublish(draft) ? "green" : "yellow"}">${isReadyToPublish(draft) ? "ready to publish" : "not ready"}</span>
            </td>
            <td>
              ${draft.concept_name ? `<small>${escapeHtml(draft.concept_name)}</small><br>` : ""}
              ${draft.source_title ? `<small>${escapeHtml(draft.source_title)}</small>` : ""}
            </td>
            <td>
              <div class="button-row">
                <span class="tag ${draftWarnings(draft).length ? "yellow" : "green"}">${warningCountLabel(draftWarnings(draft))}</span>
                ${warningTags(draft.warnings)}
              </div>
            </td>
            <td><button class="button" data-draft-open="${draft.id}" type="button">Open</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}


function renderLineage(lineage = []) {
  if (!lineage.length) return `<p class="muted">No lineage recorded for this draft.</p>`;
  return `
    <table class="data-table">
      <thead><tr><th>Source</th><th>Concept</th><th>Evidence</th><th>Reason</th></tr></thead>
      <tbody>
        ${lineage.map((row) => `
          <tr>
            <td>
              ${row.source_title ? escapeHtml(row.source_title) : `<span class="muted">No source</span>`}
              ${row.source_chunk_number ? `<br><span class="tag blue">Chunk ${row.source_chunk_number}</span>` : ""}
              ${row.source_page_number ? `<span class="tag">Page ${row.source_page_number}</span>` : ""}
              ${row.source_authority_level ? `<span class="tag">Authority ${Number(row.source_authority_level)}</span>` : ""}
              ${row.source_confidence ? `<span class="tag">${escapeHtml(row.source_confidence)}</span>` : ""}
              ${row.source_verification_status ? `<span class="tag">${escapeHtml(row.source_verification_status)}</span>` : ""}
            </td>
            <td>
              ${row.concept_name ? escapeHtml(row.concept_name) : `<span class="muted">No concept</span>`}
              ${row.concept_status ? `<br><span class="tag ${row.concept_status === "verified" ? "green" : row.concept_status === "rejected" ? "red" : "yellow"}">${escapeHtml(row.concept_status)} concept</span>` : ""}
            </td>
            <td>${escapeHtml(row.evidence_text)}</td>
            <td><span class="tag">${escapeHtml(row.lineage_reason)}</span></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}


export function renderDraftDetail(draft) {
  return `
    <section class="grid grid-2">
      <article class="card">
        <h3>Draft</h3>
        <form id="draft-edit-form" class="grid">
          <div class="field">
            <label for="draft-stem">Stem</label>
            <textarea id="draft-stem" class="textarea" name="stem">${escapeHtml(draft.stem)}</textarea>
          </div>
          <div class="grid grid-3">
            <div class="field">
              <label for="draft-course-code">Course</label>
              <input id="draft-course-code" class="input" name="course_code" value="${escapeHtml(draft.course_code)}">
            </div>
            <div class="field">
              <label for="draft-type">Type</label>
              <input id="draft-type" class="input" name="question_type" value="${escapeHtml(draft.question_type || "single_choice")}">
            </div>
            <div class="field">
              <label for="draft-status">Status</label>
              <select id="draft-status" class="course-select" name="status">${optionList(STATUS_VALUES, draft.status)}</select>
            </div>
          </div>
          <div class="grid grid-3">
            <div class="field">
              <label for="draft-difficulty">Difficulty</label>
              <input id="draft-difficulty" class="input" name="difficulty" type="number" min="1" max="5" value="${Number(draft.difficulty || 3)}">
            </div>
            <div class="field">
              <label for="draft-probability">OA probability</label>
              <input id="draft-probability" class="input" name="oa_probability" type="number" min="1" max="5" value="${Number(draft.oa_probability || 3)}">
            </div>
            <div class="field">
              <label for="draft-confidence">Confidence</label>
              <select id="draft-confidence" class="course-select" name="confidence">${optionList(CONFIDENCE_VALUES, draft.confidence)}</select>
            </div>
          </div>
          <div class="field">
            <label for="draft-choices">Choices JSON</label>
            <textarea id="draft-choices" class="textarea" name="choices">${escapeHtml(formatJson(draft.choices))}</textarea>
          </div>
          <div class="field">
            <label for="draft-answer">Correct answer JSON</label>
            <textarea id="draft-answer" class="textarea" name="correct_answer">${escapeHtml(formatJson(draft.correct_answer))}</textarea>
          </div>
          <div class="field">
            <label for="draft-explanation">Plain explanation fallback</label>
            <textarea id="draft-explanation" class="textarea" name="explanation">${escapeHtml(draft.explanation || "")}</textarea>
          </div>
          <div>
            <h3>Structured Explanation</h3>
            ${renderStructuredExplanationEditor(draft)}
          </div>
          <button class="button button-primary" type="submit">Save Draft</button>
        </form>
      </article>
      <article class="card">
        <h3>Review</h3>
        <div class="button-row">
          <span class="tag ${draftStatusClass(draft.status)}">${escapeHtml(draft.status)}</span>
          <span class="tag">${escapeHtml(draft.generation_method)}</span>
          ${draft.published_question_id ? `<span class="tag green">Published #${draft.published_question_id}</span>` : ""}
          ${draft.published_question_status ? `<span class="tag ${draftStatusClass(draft.published_question_status)}">Question ${escapeHtml(draft.published_question_status)}</span>` : ""}
        </div>
        <div class="button-row" style="margin-top: 0.85rem;">
          <button class="button" data-draft-action="review" type="button">Reviewed</button>
          <button class="button button-success" data-draft-action="verify" type="button">Verified</button>
          <button class="button button-danger" data-draft-action="reject" type="button">Rejected</button>
          <button class="button button-primary" data-draft-action="publish" type="button">Publish</button>
        </div>
        <h3 style="margin-top: 1rem;">Validation Warnings</h3>
        ${renderWarningGroups(draft.warnings)}
        <h3 style="margin-top: 1rem;">Publish History</h3>
        ${renderPublishHistory(draft.publish_history)}
      </article>
    </section>

    <section class="card" style="margin-top: 1rem;">
      <h3>Lineage</h3>
      ${renderLineage(draft.lineage)}
    </section>
  `;
}


export function publishQuestionDraft(draftId, apiPostFn = apiPost) {
  return apiPostFn(`/api/question-drafts/${draftId}/publish`, {});
}


function emptyMessage(message) {
  return `<section class="empty-state"><h2>${escapeHtml(message)}</h2></section>`;
}


async function renderDraftListView(ctx) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Question Drafts</h2>
        <p class="muted">Review draft questions before publishing to the course bank.</p>
      </div>
      <button id="draft-refresh" class="button" type="button">Refresh</button>
    </div>

    <section class="card">
      <div class="filter-grid">
        <div class="field">
          <label for="draft-search">Search</label>
          <input id="draft-search" class="input" type="search" placeholder="Stem, source, concept">
        </div>
        <div class="field slim">
          <label for="draft-status-filter">Status</label>
          <select id="draft-status-filter" class="course-select">
            <option value="">Any status</option>
            ${optionList(STATUS_VALUES)}
          </select>
        </div>
        <div class="field slim">
          <label for="draft-course-filter">Course</label>
          <input id="draft-course-filter" class="input" placeholder="SY0-701">
        </div>
        <div class="field slim">
          <label for="draft-concept-filter">Concept ID</label>
          <input id="draft-concept-filter" class="input" type="number">
        </div>
        <label class="toggle-row" style="border-bottom: 0; padding-bottom: 0;">
          <span>Warnings only</span>
          <input id="draft-warnings-only" type="checkbox">
        </label>
        <label class="toggle-row" style="border-bottom: 0; padding-bottom: 0;">
          <span>High severity</span>
          <input id="draft-high-warnings-only" type="checkbox">
        </label>
        <label class="toggle-row" style="border-bottom: 0; padding-bottom: 0;">
          <span>Show rejected</span>
          <input id="draft-include-rejected" type="checkbox">
        </label>
      </div>
    </section>

    <section class="card" style="margin-top: 1rem;">
      <div id="draft-list"><p class="muted">Loading drafts...</p></div>
    </section>
  `;

  const listPanel = ctx.root.querySelector("#draft-list");
  const searchInput = ctx.root.querySelector("#draft-search");
  const statusSelect = ctx.root.querySelector("#draft-status-filter");
  const courseInput = ctx.root.querySelector("#draft-course-filter");
  const conceptInput = ctx.root.querySelector("#draft-concept-filter");
  const warningsInput = ctx.root.querySelector("#draft-warnings-only");
  const highWarningsInput = ctx.root.querySelector("#draft-high-warnings-only");
  const rejectedInput = ctx.root.querySelector("#draft-include-rejected");
  let drafts = [];

  const currentFilters = () => ({
    search: searchInput?.value || "",
    status: statusSelect?.value || "",
    courseCode: courseInput?.value || "",
    conceptId: conceptInput?.value || "",
    warningsOnly: warningsInput?.checked || false,
    highSeverityOnly: highWarningsInput?.checked || false,
    includeRejected: rejectedInput?.checked || false
  });

  const renderRows = () => {
    if (!listPanel) return;
    listPanel.innerHTML = renderDraftList(filterDrafts(drafts, currentFilters()));
    listPanel.querySelectorAll("[data-draft-open]").forEach((button) => {
      button.addEventListener("click", () => ctx.navigate("questionDrafts", { draftId: button.dataset.draftOpen }));
    });
  };

  const loadDrafts = async () => {
    try {
      drafts = await apiGet("/api/question-drafts?include_rejected=true");
      renderRows();
    } catch (error) {
      ctx.showStatus(`Question drafts failed: ${error.message}`);
    }
  };

  [searchInput, courseInput, conceptInput].forEach((input) => input?.addEventListener("input", renderRows));
  [statusSelect, warningsInput, highWarningsInput, rejectedInput].forEach((input) => input?.addEventListener("change", renderRows));
  ctx.root.querySelector("#draft-refresh")?.addEventListener("click", loadDrafts);
  await loadDrafts();
}


async function renderDraftDetailView(ctx, draftId) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Question Draft</h2>
        <p class="muted">Loading draft...</p>
      </div>
      <button id="draft-back" class="button" type="button">All Drafts</button>
    </div>
    <section id="draft-detail"><p class="muted">Loading draft detail...</p></section>
  `;
  ctx.root.querySelector("#draft-back")?.addEventListener("click", () => ctx.navigate("questionDrafts"));

  const loadDraft = async () => {
    try {
      const draft = await apiGet(`/api/question-drafts/${draftId}`);
      const panel = ctx.root.querySelector("#draft-detail");
      if (!panel) return;
      panel.innerHTML = renderDraftDetail(draft);

      panel.querySelector("#draft-edit-form")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        try {
          await apiPut(`/api/question-drafts/${draftId}`, buildDraftPayloadFromFormData(data));
          ctx.showStatus("Draft saved.");
          await loadDraft();
        } catch (error) {
          ctx.showStatus(`Draft save failed: ${error.message}`);
        }
      });

      panel.querySelectorAll("[data-draft-action]").forEach((button) => {
        button.addEventListener("click", async () => {
          const action = button.dataset.draftAction;
          try {
            if (action === "publish") {
              await publishQuestionDraft(draftId);
            } else {
              await apiPost(`/api/question-drafts/${draftId}/${action}`, {});
            }
            ctx.showStatus(action === "publish" ? "Draft published." : `Draft marked ${action}.`);
            await loadDraft();
          } catch (error) {
            ctx.showStatus(`Draft ${action} failed: ${error.message}`);
          }
        });
      });
    } catch (error) {
      ctx.showStatus(`Question draft failed: ${error.message}`);
    }
  };

  await loadDraft();
}


export function renderQuestionDrafts(ctx) {
  if (!isBackendMode()) {
    ctx.root.innerHTML = emptyMessage("Backend login required for Question Drafts.");
    return;
  }

  if (ctx.params.draftId) {
    renderDraftDetailView(ctx, ctx.params.draftId);
    return;
  }
  renderDraftListView(ctx);
}
