import { apiDelete, apiGet, apiPost, apiPut, isBackendMode } from "./api.js";
import { renderConflictList } from "./conflicts.js";
import { renderDraftList } from "./questionDrafts.js";


const STATUS_VALUES = ["generated", "reviewed", "verified", "rejected"];
const CONFIDENCE_VALUES = ["generated", "reviewed", "verified", "unverified"];
const RELATIONSHIP_TYPES = [
  "related_to",
  "contrasts_with",
  "depends_on",
  "belongs_to",
  "example_of",
  "component_of",
  "replaces",
  "maps_to"
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


function sourceCountLabel(count) {
  const value = Number(count || 0);
  return `${value} ${value === 1 ? "source" : "sources"}`;
}


function relationshipCountLabel(count) {
  const value = Number(count || 0);
  return `${value} ${value === 1 ? "relationship" : "relationships"}`;
}


function normalizeFilter(value) {
  return String(value ?? "").trim().toLowerCase();
}


function fieldValue(fields, name, fallback = "") {
  if (fields?.get) return fields.get(name) ?? fallback;
  return fields?.[name] ?? fallback;
}


export function conceptStatusClass(status) {
  if (status === "verified") return "green";
  if (status === "reviewed") return "blue";
  if (status === "rejected") return "red";
  return "yellow";
}


export function filterConcepts(concepts, filters = {}) {
  const search = normalizeFilter(filters.search);
  const status = normalizeFilter(filters.status);
  const courseCode = normalizeFilter(filters.courseCode);
  const includeRejected = Boolean(filters.includeRejected);

  return concepts.filter((concept) => {
    if (!includeRejected && concept.status === "rejected") return false;
    if (status && concept.status !== status) return false;
    if (courseCode && normalizeFilter(concept.course_code) !== courseCode) return false;
    if (!search) return true;
    const aliases = Array.isArray(concept.aliases) ? concept.aliases.join(" ") : "";
    const haystack = normalizeFilter(`${concept.name} ${concept.normalized_name || ""} ${concept.description || ""} ${aliases}`);
    return haystack.includes(search);
  });
}


export function renderConceptTable(concepts) {
  if (!concepts.length) return `<p class="muted">No concepts match the current filters.</p>`;
  return `
    <table class="data-table">
      <thead>
        <tr><th>Name</th><th>Status</th><th>Confidence</th><th>Sources</th><th>Relationships</th><th>Actions</th></tr>
      </thead>
      <tbody>
        ${concepts.map((concept) => `
          <tr>
            <td>
              <strong>${escapeHtml(concept.name)}</strong>
              ${concept.course_code ? `<br><small>${escapeHtml(concept.course_code)}</small>` : ""}
            </td>
            <td><span class="tag ${conceptStatusClass(concept.status)}">${escapeHtml(concept.status)}</span></td>
            <td><span class="tag">${escapeHtml(concept.confidence)}</span></td>
            <td>${escapeHtml(sourceCountLabel(concept.source_count))}</td>
            <td>${escapeHtml(relationshipCountLabel(concept.relationship_count))}</td>
            <td><button class="button" data-concept-open="${concept.id}" type="button">Open</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}


export function renderAliasList(aliases, isAdmin = false) {
  if (!aliases.length) return `<p class="muted">No aliases recorded yet.</p>`;
  return `
    <table class="data-table">
      <thead><tr><th>Alias</th><th>Normalized</th>${isAdmin ? "<th>Actions</th>" : ""}</tr></thead>
      <tbody>
        ${aliases.map((alias) => `
          <tr>
            <td>${escapeHtml(alias.alias)}</td>
            <td><code>${escapeHtml(alias.normalized_alias)}</code></td>
            ${isAdmin ? `<td><button class="button button-danger" data-concept-alias-delete="${alias.id}" type="button">Delete</button></td>` : ""}
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}


export function renderEvidenceTable(evidence) {
  if (!evidence.length) return `<p class="muted">No linked source chunks yet.</p>`;
  return `
    <table class="data-table">
      <thead><tr><th>Source</th><th>Chunk</th><th>Trust</th><th>Evidence</th></tr></thead>
      <tbody>
        ${evidence.map((item) => `
          <tr>
            <td>
              ${escapeHtml(item.source_title)}
              <br><small>${escapeHtml(item.source_type)}</small>
            </td>
            <td>
              <span class="tag blue">Chunk ${item.chunk_number}</span>
              ${item.page_number ? `<span class="tag">Page ${item.page_number}</span>` : ""}
              ${item.heading ? `<br><small>${escapeHtml(item.heading)}</small>` : ""}
            </td>
            <td>
              <span class="tag">${escapeHtml(item.source_confidence)}</span>
              <span class="tag ${item.verification_status === "verified" ? "green" : "yellow"}">${escapeHtml(item.verification_status)}</span>
            </td>
            <td>${escapeHtml(item.evidence_text)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}


export function submitRelationshipForm(conceptId, fields, apiPostFn = apiPost) {
  return apiPostFn(`/api/concepts/${conceptId}/relationships`, {
    concept_b_id: Number(fieldValue(fields, "concept_b_id")),
    relationship_type: String(fieldValue(fields, "relationship_type", "related_to")),
    confidence_score: Number(fieldValue(fields, "confidence_score", 0.5)),
    status: String(fieldValue(fields, "status", "generated"))
  });
}


export function uniqueSourceConcepts(links) {
  const concepts = new Map();
  for (const link of links || []) {
    const concept = link.concept;
    if (!concept?.id) continue;
    const current = concepts.get(concept.id) || { ...concept, link_count: 0 };
    current.link_count += 1;
    concepts.set(concept.id, current);
  }
  return Array.from(concepts.values()).sort((a, b) => a.name.localeCompare(b.name));
}


export function renderSourceConceptSummary(links) {
  const concepts = uniqueSourceConcepts(links);
  if (!concepts.length) return `<p class="muted">No concepts extracted from this source yet.</p>`;
  return `
    <table class="data-table">
      <thead><tr><th>Concept</th><th>Status</th><th>Evidence</th></tr></thead>
      <tbody>
        ${concepts.map((concept) => `
          <tr>
            <td><strong>${escapeHtml(concept.name)}</strong></td>
            <td><span class="tag ${conceptStatusClass(concept.status)}">${escapeHtml(concept.status)}</span></td>
            <td>${concept.link_count} ${concept.link_count === 1 ? "chunk" : "chunks"}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}


export function extractConceptsForSource(materialId, apiPostFn = apiPost) {
  return apiPostFn(`/api/source-materials/${materialId}/extract-concepts`, {});
}


export async function handleExtractConceptsClick(materialId, {
  apiPostFn = apiPost,
  showStatus = () => {},
  reload = async () => {}
} = {}) {
  const result = await extractConceptsForSource(materialId, apiPostFn);
  showStatus(result.message || "Concept extraction completed.");
  await reload(result);
  return result;
}


function emptyMessage(message) {
  return `<section class="empty-state"><h2>${escapeHtml(message)}</h2></section>`;
}


async function renderConceptList(ctx) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Concepts</h2>
        <p class="muted">Review and manage concepts extracted from source chunks.</p>
      </div>
      <button id="concept-refresh" class="button" type="button">Refresh</button>
    </div>

    <section class="card">
      <div class="filter-grid">
        <div class="field">
          <label for="concept-search">Search</label>
          <input id="concept-search" class="input" type="search" placeholder="Concept or alias">
        </div>
        <div class="field slim">
          <label for="concept-status-filter">Status</label>
          <select id="concept-status-filter" class="course-select">
            <option value="">Any status</option>
            ${optionList(STATUS_VALUES)}
          </select>
        </div>
        <div class="field slim">
          <label for="concept-course-filter">Course</label>
          <input id="concept-course-filter" class="input" placeholder="SECPLUS">
        </div>
        <label class="toggle-row" style="border-bottom: 0; padding-bottom: 0;">
          <span>Show rejected</span>
          <input id="concept-include-rejected" type="checkbox">
        </label>
      </div>
    </section>

    <section class="card" style="margin-top: 1rem;">
      <div id="concept-list"><p class="muted">Loading concepts...</p></div>
    </section>
  `;

  const listPanel = ctx.root.querySelector("#concept-list");
  const searchInput = ctx.root.querySelector("#concept-search");
  const statusSelect = ctx.root.querySelector("#concept-status-filter");
  const courseInput = ctx.root.querySelector("#concept-course-filter");
  const rejectedInput = ctx.root.querySelector("#concept-include-rejected");
  let concepts = [];

  const currentFilters = () => ({
    search: searchInput?.value || "",
    status: statusSelect?.value || "",
    courseCode: courseInput?.value || "",
    includeRejected: rejectedInput?.checked || false
  });

  const renderRows = () => {
    if (!listPanel) return;
    listPanel.innerHTML = renderConceptTable(filterConcepts(concepts, currentFilters()));
    listPanel.querySelectorAll("[data-concept-open]").forEach((button) => {
      button.addEventListener("click", () => ctx.navigate("concepts", { conceptId: button.dataset.conceptOpen }));
    });
  };

  const loadConcepts = async () => {
    try {
      concepts = await apiGet("/api/concepts?include_rejected=true");
      renderRows();
    } catch (error) {
      ctx.showStatus(`Concepts failed: ${error.message}`);
    }
  };

  [searchInput, courseInput].forEach((input) => input?.addEventListener("input", renderRows));
  [statusSelect, rejectedInput].forEach((input) => input?.addEventListener("change", renderRows));
  ctx.root.querySelector("#concept-refresh")?.addEventListener("click", loadConcepts);
  await loadConcepts();
}


function renderRelationshipsTable(relationships, isAdmin = false) {
  if (!relationships.length) return `<p class="muted">No relationships recorded yet.</p>`;
  return `
    <table class="data-table">
      <thead><tr><th>Relationship</th><th>Concept</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>
        ${relationships.map((relationship) => `
          <tr>
            <td>${escapeHtml(relationship.relationship_type)}</td>
            <td>${escapeHtml(relationship.concept_a_name)} -> ${escapeHtml(relationship.concept_b_name)}</td>
            <td><span class="tag ${conceptStatusClass(relationship.status)}">${escapeHtml(relationship.status)}</span></td>
            <td>
              <div class="button-row">
                <button class="button" data-relationship-status="${relationship.id}:reviewed" type="button">Reviewed</button>
                <button class="button button-success" data-relationship-status="${relationship.id}:verified" type="button">Verified</button>
                <button class="button button-danger" data-relationship-status="${relationship.id}:rejected" type="button">Rejected</button>
                ${isAdmin ? `<button class="button button-danger" data-relationship-delete="${relationship.id}" type="button">Delete</button>` : ""}
              </div>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}


async function renderConceptDetail(ctx, conceptId) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Concept Detail</h2>
        <p class="muted">Loading concept...</p>
      </div>
      <button id="concept-back" class="button" type="button">All Concepts</button>
    </div>
    <section id="concept-detail"><p class="muted">Loading concept detail...</p></section>
  `;
  ctx.root.querySelector("#concept-back")?.addEventListener("click", () => ctx.navigate("concepts"));

  const loadConcept = async () => {
    const [concept, aliases, evidence, relationships, conflicts, drafts, allConcepts] = await Promise.all([
      apiGet(`/api/concepts/${conceptId}`),
      apiGet(`/api/concepts/${conceptId}/aliases`),
      apiGet(`/api/concepts/${conceptId}/evidence`),
      apiGet(`/api/concepts/${conceptId}/relationships`),
      apiGet(`/api/conflicts?concept_id=${conceptId}&include_resolved=true`),
      apiGet(`/api/question-drafts?concept_id=${conceptId}&include_rejected=true`),
      apiGet("/api/concepts?include_rejected=true")
    ]);
    const panel = ctx.root.querySelector("#concept-detail");
    if (!panel) return;
    const isAdmin = ctx.app.user?.role === "admin";
    const unresolvedConflicts = conflicts.filter((conflict) => !["resolved", "rejected"].includes(conflict.status));
    const activeDrafts = drafts.filter((draft) => draft.status !== "rejected");
    const activeConceptOptions = allConcepts
      .filter((item) => Number(item.id) !== Number(conceptId) && item.status !== "rejected")
      .map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`)
      .join("");
    const mergeConceptOptions = allConcepts
      .filter((item) => Number(item.id) !== Number(conceptId))
      .map((item) => `<option value="${item.id}">${escapeHtml(item.name)} (${escapeHtml(item.status)})</option>`)
      .join("");
    panel.innerHTML = `
      <section class="grid grid-2">
        <article class="card">
          <h3>${escapeHtml(concept.name)}</h3>
          <form id="concept-edit-form" class="grid">
            <div class="field">
              <label for="concept-name">Name</label>
              <input id="concept-name" class="input" name="name" value="${escapeHtml(concept.name)}" required>
            </div>
            <div class="field">
              <label for="concept-description">Description</label>
              <textarea id="concept-description" class="textarea" name="description">${escapeHtml(concept.description || "")}</textarea>
            </div>
            <div class="grid grid-3">
              <div class="field">
                <label for="concept-status">Status</label>
                <select id="concept-status" class="course-select" name="status">${optionList(STATUS_VALUES, concept.status)}</select>
              </div>
              <div class="field">
                <label for="concept-confidence">Confidence</label>
                <select id="concept-confidence" class="course-select" name="confidence">${optionList(CONFIDENCE_VALUES, concept.confidence)}</select>
              </div>
              <div class="field">
                <label for="concept-course-code">Course</label>
                <input id="concept-course-code" class="input" name="course_code" value="${escapeHtml(concept.course_code || "")}">
              </div>
            </div>
            <button class="button button-primary" type="submit">Save Concept</button>
          </form>
        </article>
        <article class="card">
          <h3>Review</h3>
          <div class="button-row">
            <span class="tag ${conceptStatusClass(concept.status)}">${escapeHtml(concept.status)}</span>
            <span class="tag">${escapeHtml(concept.confidence)}</span>
            <span class="tag blue">${escapeHtml(sourceCountLabel(concept.source_count))}</span>
            <span class="tag blue">${escapeHtml(relationshipCountLabel(concept.relationship_count))}</span>
            <span class="tag ${unresolvedConflicts.length ? "red" : "green"}">${unresolvedConflicts.length} unresolved conflicts</span>
            <span class="tag ${activeDrafts.length ? "blue" : "yellow"}">${activeDrafts.length} drafts</span>
          </div>
          <div class="button-row" style="margin-top: 0.9rem;">
            <button class="button" data-concept-review-status="reviewed" type="button">Reviewed</button>
            <button class="button button-success" data-concept-review-status="verified" type="button">Verified</button>
            <button class="button button-danger" data-concept-review-status="rejected" type="button">Rejected</button>
            ${concept.status === "rejected" ? `<button class="button" data-concept-review-status="restore" type="button">Restore</button>` : ""}
            <button id="concept-detect-conflicts" class="button" type="button">Detect Conflicts</button>
            <button id="concept-draft-questions" class="button" type="button">Draft Questions</button>
          </div>
        </article>
      </section>

      <section class="grid grid-2" style="margin-top: 1rem;">
        <article class="card">
          <h3>Aliases</h3>
          <form id="concept-alias-form" class="button-row" style="margin-bottom: 0.75rem;">
            <input class="input" name="alias" placeholder="Add alias" required>
            <button class="button" type="submit">Add Alias</button>
          </form>
          ${renderAliasList(aliases, isAdmin)}
        </article>
        <article class="card">
          <h3>Merge Concept</h3>
          <form id="concept-merge-form" class="grid">
            <div class="field">
              <label for="concept-merge-target">Target concept</label>
              <select id="concept-merge-target" class="course-select" name="target_concept_id" ${mergeConceptOptions ? "" : "disabled"}>
                ${mergeConceptOptions || `<option value="">No merge targets</option>`}
              </select>
            </div>
            <button class="button button-danger" type="submit" ${mergeConceptOptions ? "" : "disabled"}>Merge Into Target</button>
          </form>
        </article>
      </section>

      <section class="card" style="margin-top: 1rem;">
        <h3>Evidence</h3>
        ${renderEvidenceTable(evidence)}
      </section>

      <section class="card" style="margin-top: 1rem;">
        <h3>Related Conflicts</h3>
        ${renderConflictList(conflicts)}
      </section>

      <section class="card" style="margin-top: 1rem;">
        <h3>Question Drafts</h3>
        ${renderDraftList(drafts)}
      </section>

      <section class="card" style="margin-top: 1rem;">
        <h3>Relationships</h3>
        <form id="concept-relationship-form" class="filter-grid" style="margin-bottom: 0.75rem;">
          <div class="field">
            <label for="relationship-target">Concept</label>
            <select id="relationship-target" class="course-select" name="concept_b_id" ${activeConceptOptions ? "" : "disabled"}>
              ${activeConceptOptions || `<option value="">No concepts available</option>`}
            </select>
          </div>
          <div class="field">
            <label for="relationship-type">Type</label>
            <select id="relationship-type" class="course-select" name="relationship_type">${optionList(RELATIONSHIP_TYPES, "related_to")}</select>
          </div>
          <div class="field slim">
            <label for="relationship-confidence">Confidence</label>
            <input id="relationship-confidence" class="input" name="confidence_score" type="number" min="0" max="1" step="0.05" value="0.5">
          </div>
          <button class="button" type="submit" ${activeConceptOptions ? "" : "disabled"}>Add Relationship</button>
        </form>
        ${renderRelationshipsTable(relationships, isAdmin)}
      </section>
    `;

    panel.querySelector("#concept-edit-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const data = new FormData(form);
      try {
        await apiPut(`/api/concepts/${conceptId}`, {
          name: String(data.get("name") || ""),
          description: String(data.get("description") || ""),
          status: String(data.get("status") || "generated"),
          confidence: String(data.get("confidence") || "unverified"),
          course_code: String(data.get("course_code") || "") || null
        });
        ctx.showStatus("Concept saved.");
        await loadConcept();
      } catch (error) {
        ctx.showStatus(`Concept save failed: ${error.message}`);
      }
    });

    panel.querySelectorAll("[data-concept-review-status]").forEach((button) => {
      button.addEventListener("click", async () => {
        const nextStatus = button.dataset.conceptReviewStatus;
        try {
          if (nextStatus === "restore") {
            await apiPost(`/api/concepts/${conceptId}/restore`, {});
          } else {
            await apiPost(`/api/concepts/${conceptId}/${nextStatus === "reviewed" ? "review" : nextStatus === "verified" ? "verify" : "reject"}`, {});
          }
          ctx.showStatus(`Concept marked ${nextStatus}.`);
          await loadConcept();
        } catch (error) {
          ctx.showStatus(`Concept review failed: ${error.message}`);
        }
      });
    });

    panel.querySelector("#concept-detect-conflicts")?.addEventListener("click", async () => {
      try {
        const result = await apiPost(`/api/concepts/${conceptId}/detect-conflicts`, {});
        ctx.showStatus(result.message || "Conflict detection completed.");
        await loadConcept();
      } catch (error) {
        ctx.showStatus(`Conflict detection failed: ${error.message}`);
      }
    });

    panel.querySelector("#concept-draft-questions")?.addEventListener("click", async () => {
      try {
        const result = await apiPost(`/api/concepts/${conceptId}/draft-questions`, {
          course_code: concept.course_code || ctx.bundle?.meta?.id || ctx.app.course?.id || undefined
        });
        ctx.showStatus(`Created ${result.drafts_created || 0} question drafts.`);
        await loadConcept();
      } catch (error) {
        ctx.showStatus(`Question drafting failed: ${error.message}`);
      }
    });

    panel.querySelector("#concept-alias-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const data = new FormData(form);
      try {
        await apiPost(`/api/concepts/${conceptId}/aliases`, { alias: String(data.get("alias") || "") });
        form.reset();
        ctx.showStatus("Alias added.");
        await loadConcept();
      } catch (error) {
        ctx.showStatus(`Alias add failed: ${error.message}`);
      }
    });

    panel.querySelectorAll("[data-concept-alias-delete]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await apiDelete(`/api/concepts/${conceptId}/aliases/${button.dataset.conceptAliasDelete}`);
          ctx.showStatus("Alias deleted.");
          await loadConcept();
        } catch (error) {
          ctx.showStatus(`Alias delete failed: ${error.message}`);
        }
      });
    });

    panel.querySelector("#concept-relationship-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await submitRelationshipForm(conceptId, new FormData(event.currentTarget));
        ctx.showStatus("Relationship added.");
        await loadConcept();
      } catch (error) {
        ctx.showStatus(`Relationship add failed: ${error.message}`);
      }
    });

    panel.querySelectorAll("[data-relationship-status]").forEach((button) => {
      button.addEventListener("click", async () => {
        const [relationshipId, nextStatus] = String(button.dataset.relationshipStatus || "").split(":");
        try {
          await apiPut(`/api/concept-relationships/${relationshipId}`, { status: nextStatus });
          ctx.showStatus(`Relationship marked ${nextStatus}.`);
          await loadConcept();
        } catch (error) {
          ctx.showStatus(`Relationship update failed: ${error.message}`);
        }
      });
    });

    panel.querySelectorAll("[data-relationship-delete]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await apiDelete(`/api/concept-relationships/${button.dataset.relationshipDelete}`);
          ctx.showStatus("Relationship deleted.");
          await loadConcept();
        } catch (error) {
          ctx.showStatus(`Relationship delete failed: ${error.message}`);
        }
      });
    });

    panel.querySelector("#concept-merge-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      const targetId = Number(data.get("target_concept_id"));
      if (!targetId) return;
      try {
        await apiPost(`/api/concepts/${conceptId}/merge`, { target_concept_id: targetId });
        ctx.showStatus("Concept merged.");
        await loadConcept();
      } catch (error) {
        ctx.showStatus(`Concept merge failed: ${error.message}`);
      }
    });

    panel.querySelectorAll("[data-conflict-open]").forEach((button) => {
      button.addEventListener("click", () => ctx.navigate("conflicts", { conflictId: button.dataset.conflictOpen }));
    });
    panel.querySelectorAll("[data-draft-open]").forEach((button) => {
      button.addEventListener("click", () => ctx.navigate("questionDrafts", { draftId: button.dataset.draftOpen }));
    });
  };

  try {
    await loadConcept();
  } catch (error) {
    ctx.showStatus(`Concept detail failed: ${error.message}`);
  }
}


export function renderConcepts(ctx) {
  if (!isBackendMode()) {
    ctx.root.innerHTML = emptyMessage("Backend login required for Concepts.");
    return;
  }

  if (ctx.params.conceptId) {
    renderConceptDetail(ctx, ctx.params.conceptId);
    return;
  }
  renderConceptList(ctx);
}
