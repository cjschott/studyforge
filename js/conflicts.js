import { apiGet, apiPost, apiPut, isBackendMode } from "./api.js";


const SEVERITY_VALUES = ["low", "medium", "high"];
const STATUS_VALUES = ["generated", "needs_review", "reviewed", "resolved", "rejected"];
const CONFLICT_TYPES = [
  "conflicting_definition",
  "conflicting_answer",
  "outdated_reference",
  "unsupported_claim",
  "duplicate_concept",
  "low_authority_source",
  "missing_lineage",
  "unclear_explanation",
  "possible_bad_answer"
];


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


export function severityClass(severity) {
  if (severity === "high") return "red";
  if (severity === "medium") return "yellow";
  return "blue";
}


export function conflictStatusClass(status) {
  if (status === "resolved") return "green";
  if (status === "rejected") return "red";
  if (status === "reviewed") return "blue";
  return "yellow";
}


export function filterConflicts(conflicts, filters = {}) {
  const severity = normalizeFilter(filters.severity);
  const status = normalizeFilter(filters.status);
  const conflictType = normalizeFilter(filters.conflictType);
  const search = normalizeFilter(filters.search);
  const includeResolved = Boolean(filters.includeResolved);

  return conflicts.filter((conflict) => {
    if (!includeResolved && conflict.status === "resolved") return false;
    if (severity && conflict.severity !== severity) return false;
    if (status && conflict.status !== status) return false;
    if (conflictType && conflict.conflict_type !== conflictType) return false;
    if (!search) return true;
    const haystack = normalizeFilter(`${conflict.summary} ${conflict.evidence_a} ${conflict.evidence_b} ${conflict.concept_name || ""} ${conflict.source_title_a || ""} ${conflict.source_title_b || ""}`);
    return haystack.includes(search);
  });
}


export function renderConflictList(conflicts) {
  if (!conflicts.length) return `<p class="muted">No conflicts match the current filters.</p>`;
  return `
    <table class="data-table">
      <thead><tr><th>Summary</th><th>Type</th><th>Severity</th><th>Status</th><th>Links</th><th>Actions</th></tr></thead>
      <tbody>
        ${conflicts.map((conflict) => `
          <tr>
            <td><strong>${escapeHtml(conflict.summary)}</strong></td>
            <td><span class="tag">${escapeHtml(conflict.conflict_type)}</span></td>
            <td><span class="tag ${severityClass(conflict.severity)}">${escapeHtml(conflict.severity)}</span></td>
            <td><span class="tag ${conflictStatusClass(conflict.status)}">${escapeHtml(conflict.status)}</span></td>
            <td>
              ${conflict.concept_name ? `<small>${escapeHtml(conflict.concept_name)}</small><br>` : ""}
              ${conflict.source_title_a ? `<small>${escapeHtml(conflict.source_title_a)}</small>` : ""}
              ${conflict.source_title_b ? `<br><small>${escapeHtml(conflict.source_title_b)}</small>` : ""}
            </td>
            <td><button class="button" data-conflict-open="${conflict.id}" type="button">Open</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}


function sourceMeta(conflict, side) {
  const suffix = side === "a" ? "_a" : "_b";
  const title = conflict[`source_title${suffix}`];
  if (!title) return `<p class="muted">No second source linked.</p>`;
  const chunkNumber = conflict[`source_chunk_number${suffix}`];
  const pageNumber = conflict[`source_page_number${suffix}`];
  return `
    <div class="button-row">
      <span class="tag">${escapeHtml(conflict[`source_type${suffix}`] || "")}</span>
      <span class="tag yellow">Authority ${escapeHtml(conflict[`source_authority_level${suffix}`] || "")}</span>
      <span class="tag">${escapeHtml(conflict[`source_confidence${suffix}`] || "")}</span>
      <span class="tag ${conflict[`source_verification_status${suffix}`] === "verified" ? "green" : "yellow"}">${escapeHtml(conflict[`source_verification_status${suffix}`] || "")}</span>
      ${chunkNumber ? `<span class="tag blue">Chunk ${chunkNumber}</span>` : ""}
      ${pageNumber ? `<span class="tag">Page ${pageNumber}</span>` : ""}
    </div>
    <p><strong>${escapeHtml(title)}</strong></p>
  `;
}


export function renderConflictDetail(conflict) {
  return `
    <section class="grid grid-2">
      <article class="card">
        <h3>${escapeHtml(conflict.summary)}</h3>
        <div class="button-row">
          <span class="tag">${escapeHtml(conflict.conflict_type)}</span>
          <span class="tag ${severityClass(conflict.severity)}">${escapeHtml(conflict.severity)}</span>
          <span class="tag ${conflictStatusClass(conflict.status)}">${escapeHtml(conflict.status)}</span>
          <span class="tag">${escapeHtml(conflict.detection_method || "")}</span>
        </div>
        ${conflict.concept_name ? `<p class="muted" style="margin-top: 0.75rem;">Concept: ${escapeHtml(conflict.concept_name)}</p>` : ""}
      </article>
      <article class="card">
        <h3>Actions</h3>
        <div class="button-row">
          <button class="button" data-conflict-status="reviewed" type="button">Mark Reviewed</button>
          <button class="button button-success" data-conflict-resolve type="button">Resolve</button>
          <button class="button button-danger" data-conflict-status="rejected" type="button">Reject</button>
        </div>
        <form id="conflict-note-form" class="grid" style="margin-top: 0.85rem;">
          <div class="field">
            <label for="conflict-note">Note</label>
            <textarea id="conflict-note" class="textarea" name="note"></textarea>
          </div>
          <button class="button" type="submit">Add Note</button>
        </form>
      </article>
    </section>
    <section class="grid grid-2" style="margin-top: 1rem;">
      <article class="card">
        <h3>Evidence A</h3>
        ${sourceMeta(conflict, "a")}
        <p>${escapeHtml(conflict.evidence_a)}</p>
      </article>
      <article class="card">
        <h3>Evidence B</h3>
        ${sourceMeta(conflict, "b")}
        <p>${escapeHtml(conflict.evidence_b)}</p>
      </article>
    </section>
  `;
}


export function resolveConflict(conflictId, apiPostFn = apiPost) {
  return apiPostFn(`/api/conflicts/${conflictId}/resolve`, {});
}


export function rejectConflict(conflictId, apiPutFn = apiPut) {
  return apiPutFn(`/api/conflicts/${conflictId}`, { status: "rejected" });
}


function emptyMessage(message) {
  return `<section class="empty-state"><h2>${escapeHtml(message)}</h2></section>`;
}


async function renderConflictListView(ctx) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Conflicts</h2>
        <p class="muted">Review source validation and concept conflict findings.</p>
      </div>
      <button id="conflict-refresh" class="button" type="button">Refresh</button>
    </div>

    <section class="card">
      <div class="filter-grid">
        <div class="field">
          <label for="conflict-search">Search</label>
          <input id="conflict-search" class="input" type="search" placeholder="Summary, source, evidence">
        </div>
        <div class="field slim">
          <label for="conflict-severity-filter">Severity</label>
          <select id="conflict-severity-filter" class="course-select">
            <option value="">Any severity</option>
            ${optionList(SEVERITY_VALUES)}
          </select>
        </div>
        <div class="field slim">
          <label for="conflict-status-filter">Status</label>
          <select id="conflict-status-filter" class="course-select">
            <option value="">Any status</option>
            ${optionList(STATUS_VALUES)}
          </select>
        </div>
        <div class="field">
          <label for="conflict-type-filter">Type</label>
          <select id="conflict-type-filter" class="course-select">
            <option value="">Any type</option>
            ${optionList(CONFLICT_TYPES)}
          </select>
        </div>
        <label class="toggle-row" style="border-bottom: 0; padding-bottom: 0;">
          <span>Show resolved</span>
          <input id="conflict-include-resolved" type="checkbox">
        </label>
      </div>
    </section>

    <section class="card" style="margin-top: 1rem;">
      <div id="conflict-list"><p class="muted">Loading conflicts...</p></div>
    </section>
  `;

  const listPanel = ctx.root.querySelector("#conflict-list");
  const searchInput = ctx.root.querySelector("#conflict-search");
  const severitySelect = ctx.root.querySelector("#conflict-severity-filter");
  const statusSelect = ctx.root.querySelector("#conflict-status-filter");
  const typeSelect = ctx.root.querySelector("#conflict-type-filter");
  const includeResolvedInput = ctx.root.querySelector("#conflict-include-resolved");
  let conflicts = [];

  const currentFilters = () => ({
    search: searchInput?.value || "",
    severity: severitySelect?.value || "",
    status: statusSelect?.value || "",
    conflictType: typeSelect?.value || "",
    includeResolved: includeResolvedInput?.checked || false
  });

  const renderRows = () => {
    if (!listPanel) return;
    listPanel.innerHTML = renderConflictList(filterConflicts(conflicts, currentFilters()));
    listPanel.querySelectorAll("[data-conflict-open]").forEach((button) => {
      button.addEventListener("click", () => ctx.navigate("conflicts", { conflictId: button.dataset.conflictOpen }));
    });
  };

  const loadConflicts = async () => {
    try {
      conflicts = await apiGet("/api/conflicts?include_resolved=true");
      renderRows();
    } catch (error) {
      ctx.showStatus(`Conflicts failed: ${error.message}`);
    }
  };

  [searchInput].forEach((input) => input?.addEventListener("input", renderRows));
  [severitySelect, statusSelect, typeSelect, includeResolvedInput].forEach((input) => input?.addEventListener("change", renderRows));
  ctx.root.querySelector("#conflict-refresh")?.addEventListener("click", loadConflicts);
  await loadConflicts();
}


async function renderConflictDetailView(ctx, conflictId) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Conflict Detail</h2>
        <p class="muted">Loading conflict...</p>
      </div>
      <button id="conflict-back" class="button" type="button">All Conflicts</button>
    </div>
    <section id="conflict-detail"><p class="muted">Loading conflict detail...</p></section>
  `;
  ctx.root.querySelector("#conflict-back")?.addEventListener("click", () => ctx.navigate("conflicts"));

  const loadConflict = async () => {
    try {
      const conflict = await apiGet(`/api/conflicts/${conflictId}`);
      const panel = ctx.root.querySelector("#conflict-detail");
      if (!panel) return;
      panel.innerHTML = renderConflictDetail(conflict);

      panel.querySelector("[data-conflict-resolve]")?.addEventListener("click", async () => {
        try {
          await resolveConflict(conflictId);
          ctx.showStatus("Conflict resolved.");
          await loadConflict();
        } catch (error) {
          ctx.showStatus(`Resolve failed: ${error.message}`);
        }
      });
      panel.querySelectorAll("[data-conflict-status]").forEach((button) => {
        button.addEventListener("click", async () => {
          try {
            await apiPut(`/api/conflicts/${conflictId}`, { status: button.dataset.conflictStatus });
            ctx.showStatus(`Conflict marked ${button.dataset.conflictStatus}.`);
            await loadConflict();
          } catch (error) {
            ctx.showStatus(`Conflict update failed: ${error.message}`);
          }
        });
      });
      panel.querySelector("#conflict-note-form")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const note = String(new FormData(event.currentTarget).get("note") || "").trim();
        if (!note) return;
        try {
          await apiPut(`/api/conflicts/${conflictId}`, { summary: `${conflict.summary}\nNote: ${note}` });
          ctx.showStatus("Conflict note added.");
          await loadConflict();
        } catch (error) {
          ctx.showStatus(`Conflict note failed: ${error.message}`);
        }
      });
    } catch (error) {
      ctx.showStatus(`Conflict detail failed: ${error.message}`);
    }
  };

  await loadConflict();
}


export function renderConflicts(ctx) {
  if (!isBackendMode()) {
    ctx.root.innerHTML = emptyMessage("Backend login required for Conflicts.");
    return;
  }

  if (ctx.params.conflictId) {
    renderConflictDetailView(ctx, ctx.params.conflictId);
    return;
  }
  renderConflictListView(ctx);
}
