import { apiGet, apiPost, isBackendMode } from "./api.js";
import { draftWarnings, isReadyToPublish } from "./questionDrafts.js";


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


export function selectedMaterialIdsFromFormData(formData) {
  return formData
    .getAll("source_material_ids")
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}


export function buildCourseBuilderSelection(materials, selectedIds) {
  const selectedSet = new Set(selectedIds.map((value) => Number(value)));
  const selected = materials.filter((material) => selectedSet.has(Number(material.id)));
  const totalChunks = selected.reduce((total, material) => total + Number(material.chunk_count || 0), 0);
  const conceptsById = new Map();
  const conflictsById = new Map();
  const draftsById = new Map();
  let countedConcepts = 0;
  let countedVerifiedConcepts = 0;
  let countedRejectedConcepts = 0;
  let countedRelationships = 0;
  let countedConflicts = 0;
  let countedUnresolvedConflicts = 0;
  let countedHighSeverityConflicts = 0;
  let countedDrafts = 0;
  let countedReadyForReviewDrafts = 0;
  let countedVerifiedDrafts = 0;
  let countedWarningCount = 0;
  let countedReadyToPublishDrafts = 0;
  let countedPublishedDrafts = 0;
  let countedRetiredQuestions = 0;
  selected.forEach((material) => {
    if (Array.isArray(material.concepts)) {
      material.concepts.forEach((concept) => {
        if (concept?.id) conceptsById.set(Number(concept.id), concept);
      });
    } else if (Array.isArray(material.concept_ids)) {
      material.concept_ids.forEach((id) => conceptsById.set(Number(id), { id: Number(id) }));
    } else {
      countedConcepts += Number(material.concept_count || 0);
      countedVerifiedConcepts += Number(material.verified_concept_count || 0);
      countedRejectedConcepts += Number(material.rejected_concept_count || 0);
      countedRelationships += Number(material.relationship_count || 0);
    }
    if (Array.isArray(material.conflicts)) {
      material.conflicts.forEach((conflict, index) => {
        const key = conflict?.id ? Number(conflict.id) : `${material.id}:${index}`;
        conflictsById.set(key, conflict);
      });
    } else {
      countedConflicts += Number(material.conflict_count || 0);
      countedUnresolvedConflicts += Number(material.unresolved_conflict_count || 0);
      countedHighSeverityConflicts += Number(material.high_severity_conflict_count || 0);
    }
    if (Array.isArray(material.drafts)) {
      material.drafts.forEach((draft, index) => {
        const key = draft?.id ? Number(draft.id) : `${material.id}:${index}`;
        draftsById.set(key, draft);
      });
    } else {
      countedDrafts += Number(material.draft_count || 0);
      countedReadyForReviewDrafts += Number(material.ready_for_review_draft_count || 0);
      countedVerifiedDrafts += Number(material.verified_draft_count || 0);
      countedWarningCount += Number(material.draft_warning_count || material.warning_count || 0);
      countedReadyToPublishDrafts += Number(material.ready_to_publish_draft_count || 0);
      countedPublishedDrafts += Number(material.published_draft_count || 0);
      countedRetiredQuestions += Number(material.retired_question_count || 0);
    }
  });
  const uniqueConcepts = Array.from(conceptsById.values());
  const uniqueConflicts = Array.from(conflictsById.values());
  const uniqueDrafts = Array.from(draftsById.values());
  const unresolvedStatuses = new Set(["resolved", "rejected"]);
  const unresolvedConflicts = uniqueConflicts.filter((conflict) => !unresolvedStatuses.has(conflict.status));
  const highSeverityConflicts = unresolvedConflicts.filter((conflict) => conflict.severity === "high");
  const totalConcepts = uniqueConcepts.length || countedConcepts;
  const verifiedConcepts = uniqueConcepts.length
    ? uniqueConcepts.filter((concept) => concept.status === "verified").length
    : countedVerifiedConcepts;
  const rejectedConcepts = uniqueConcepts.length
    ? uniqueConcepts.filter((concept) => concept.status === "rejected").length
    : countedRejectedConcepts;
  const relationshipCount = uniqueConcepts.length
    ? uniqueConcepts.reduce((total, concept) => total + Number(concept.relationship_count || 0), 0)
    : countedRelationships;
  const conflictCount = uniqueConflicts.length + countedConflicts;
  const unresolvedConflictCount = unresolvedConflicts.length + countedUnresolvedConflicts;
  const highSeverityConflictCount = highSeverityConflicts.length + countedHighSeverityConflicts;
  const draftCount = uniqueDrafts.length + countedDrafts;
  const readyForReviewDraftCount = uniqueDrafts.filter((draft) => draft.status === "needs_review").length + countedReadyForReviewDrafts;
  const verifiedDraftCount = uniqueDrafts.filter((draft) => draft.status === "verified").length + countedVerifiedDrafts;
  const warningCount = uniqueDrafts.reduce((total, draft) => total + draftWarnings(draft).length, 0) + countedWarningCount;
  const readyToPublishDraftCount = uniqueDrafts.filter((draft) => isReadyToPublish(draft)).length + countedReadyToPublishDrafts;
  const publishedDraftCount = uniqueDrafts.filter((draft) => draft.status === "published").length + countedPublishedDrafts;
  const retiredQuestionCount = uniqueDrafts.filter((draft) => draft.published_question_status === "retired").length + countedRetiredQuestions;
  const exportReady = highSeverityConflictCount === 0 && warningCount === 0;
  const readyCount = selected.filter((material) => material.extraction_status === "completed" && Number(material.chunk_count || 0) > 0).length;
  const missingExtractionCount = selected.length - readyCount;
  const sourceTypes = Array.from(new Set(selected.map((material) => material.source_type).filter(Boolean))).sort();

  return {
    materialIds: selected.map((material) => Number(material.id)),
    materials: selected,
    totalChunks,
    totalConcepts,
    verifiedConcepts,
    rejectedConcepts,
    relationshipCount,
    conflictCount,
    unresolvedConflictCount,
    highSeverityConflictCount,
    draftCount,
    readyForReviewDraftCount,
    verifiedDraftCount,
    warningCount,
    readyToPublishDraftCount,
    publishedDraftCount,
    retiredQuestionCount,
    exportReady,
    hasHighSeverityConflicts: highSeverityConflictCount > 0,
    readyCount,
    missingExtractionCount,
    sourceTypes,
    conceptExtractionActive: totalConcepts > 0,
    conceptLabel: `${totalConcepts} ${totalConcepts === 1 ? "concept" : "concepts"}`,
    verifiedConceptLabel: `${verifiedConcepts} verified`,
    rejectedConceptLabel: `${rejectedConcepts} rejected`,
    relationshipLabel: `${relationshipCount} ${relationshipCount === 1 ? "relationship" : "relationships"}`,
    conflictLabel: `${unresolvedConflictCount} unresolved ${unresolvedConflictCount === 1 ? "conflict" : "conflicts"}`,
    draftLabel: `${draftCount} ${draftCount === 1 ? "draft" : "drafts"}`,
    readyForReviewDraftLabel: `${readyForReviewDraftCount} ready for review`,
    verifiedDraftLabel: `${verifiedDraftCount} ${verifiedDraftCount === 1 ? "verified draft" : "verified drafts"}`,
    warningLabel: `${warningCount} ${warningCount === 1 ? "warning" : "warnings"}`,
    readyToPublishDraftLabel: `${readyToPublishDraftCount} ready to publish`,
    publishedDraftLabel: `${publishedDraftCount} published`,
    retiredQuestionLabel: `${retiredQuestionCount} retired`,
    exportReadinessLabel: exportReady ? "export ready" : "export blocked",
    contextLabel: `${selected.length} ${selected.length === 1 ? "source" : "sources"}, ${totalChunks} ${totalChunks === 1 ? "chunk" : "chunks"}`
  };
}


export async function attachConceptCounts(materials, apiGetFn = apiGet) {
  const enrichedMaterials = [];
  for (const material of materials) {
    try {
      const links = await apiGetFn(`/api/source-materials/${material.id}/concepts?include_rejected=true`);
      let conflicts = [];
      let drafts = [];
      try {
        conflicts = await apiGetFn(`/api/conflicts?source_id=${material.id}&include_resolved=true`);
      } catch (error) {
        conflicts = [];
      }
      try {
        drafts = await apiGetFn(`/api/question-drafts?source_id=${material.id}&include_rejected=true`);
      } catch (error) {
        drafts = [];
      }
      const conceptMap = new Map();
      (links || []).forEach((link) => {
        if (link.concept?.id) conceptMap.set(Number(link.concept.id), link.concept);
      });
      const concepts = Array.from(conceptMap.values()).sort((a, b) => a.name.localeCompare(b.name));
      const conceptIds = concepts.map((concept) => Number(concept.id));
      const unresolvedStatuses = new Set(["resolved", "rejected"]);
      const unresolvedConflicts = (conflicts || []).filter((conflict) => !unresolvedStatuses.has(conflict.status));
      const draftList = drafts || [];
      enrichedMaterials.push({
        ...material,
        concepts,
        conflicts: conflicts || [],
        drafts: draftList,
        concept_count: concepts.length,
        verified_concept_count: concepts.filter((concept) => concept.status === "verified").length,
        rejected_concept_count: concepts.filter((concept) => concept.status === "rejected").length,
        relationship_count: concepts.reduce((total, concept) => total + Number(concept.relationship_count || 0), 0),
        conflict_count: (conflicts || []).length,
        unresolved_conflict_count: unresolvedConflicts.length,
        high_severity_conflict_count: unresolvedConflicts.filter((conflict) => conflict.severity === "high").length,
        draft_count: draftList.length,
        ready_for_review_draft_count: draftList.filter((draft) => draft.status === "needs_review").length,
        verified_draft_count: draftList.filter((draft) => draft.status === "verified").length,
        draft_warning_count: draftList.reduce((total, draft) => total + draftWarnings(draft).length, 0),
        ready_to_publish_draft_count: draftList.filter((draft) => isReadyToPublish(draft)).length,
        published_draft_count: draftList.filter((draft) => draft.status === "published").length,
        retired_question_count: draftList.filter((draft) => draft.published_question_status === "retired").length,
        concept_ids: conceptIds
      });
    } catch (error) {
      enrichedMaterials.push({
        ...material,
        concepts: [],
        conflicts: [],
        drafts: [],
        concept_count: 0,
        verified_concept_count: 0,
        rejected_concept_count: 0,
        relationship_count: 0,
        conflict_count: 0,
        unresolved_conflict_count: 0,
        high_severity_conflict_count: 0,
        draft_count: 0,
        ready_for_review_draft_count: 0,
        verified_draft_count: 0,
        draft_warning_count: 0,
        ready_to_publish_draft_count: 0,
        published_draft_count: 0,
        retired_question_count: 0,
        concept_ids: []
      });
    }
  }
  return enrichedMaterials;
}


export function renderHighSeverityConflictWarning(selection) {
  if (!selection?.hasHighSeverityConflicts) return "";
  return `
    <div class="warning-list" style="margin-top: 0.85rem;">
      <strong>High-severity conflicts exist. Review before generating course content.</strong>
    </div>
  `;
}


export function renderExportReadiness(selection) {
  const ready = Boolean(selection?.exportReady);
  return `
    <div class="button-row" style="margin-top: 0.85rem;">
      <span class="tag ${ready ? "green" : "red"}">${escapeHtml(selection?.exportReadinessLabel || (ready ? "export ready" : "export blocked"))}</span>
      <span class="tag ${Number(selection?.warningCount || 0) ? "yellow" : "green"}">${Number(selection?.warningCount || 0)} export warnings</span>
    </div>
  `;
}


function renderStaticCourseBuilder(ctx) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Course Builder</h2>
        <p class="muted">A workspace for turning source material into reusable StudyForge course packs.</p>
      </div>
      <button class="button" type="button" disabled>Backend Required</button>
    </div>

    <section class="card">
      <h3>Static App Limitation</h3>
      <p class="muted">Source selection requires backend login because source libraries, uploads, extraction jobs, and chunks live in SQLite.</p>
    </section>
  `;
}


function renderSelectionSummary(panel, selection) {
  panel.innerHTML = `
    <h3>Selected Context</h3>
    <div class="button-row">
      <span class="tag blue">${escapeHtml(selection.contextLabel)}</span>
      <span class="tag ${selection.totalConcepts ? "green" : "yellow"}">${escapeHtml(selection.conceptLabel)}</span>
      <span class="tag green">${escapeHtml(selection.verifiedConceptLabel)}</span>
      <span class="tag ${selection.rejectedConcepts ? "red" : "yellow"}">${escapeHtml(selection.rejectedConceptLabel)}</span>
      <span class="tag blue">${escapeHtml(selection.relationshipLabel)}</span>
      <span class="tag ${selection.unresolvedConflictCount ? "red" : "green"}">${escapeHtml(selection.conflictLabel)}</span>
      <span class="tag ${selection.draftCount ? "blue" : "yellow"}">${escapeHtml(selection.draftLabel)}</span>
      <span class="tag ${selection.readyForReviewDraftCount ? "yellow" : "green"}">${escapeHtml(selection.readyForReviewDraftLabel)}</span>
      <span class="tag ${selection.verifiedDraftCount ? "green" : "yellow"}">${escapeHtml(selection.verifiedDraftLabel)}</span>
      <span class="tag ${selection.warningCount ? "yellow" : "green"}">${escapeHtml(selection.warningLabel)}</span>
      <span class="tag ${selection.readyToPublishDraftCount ? "green" : "yellow"}">${escapeHtml(selection.readyToPublishDraftLabel)}</span>
      <span class="tag ${selection.publishedDraftCount ? "green" : "yellow"}">${escapeHtml(selection.publishedDraftLabel)}</span>
      <span class="tag ${selection.retiredQuestionCount ? "red" : "green"}">${escapeHtml(selection.retiredQuestionLabel)}</span>
      <span class="tag green">${selection.readyCount} ready</span>
      ${selection.missingExtractionCount ? `<span class="tag yellow">${selection.missingExtractionCount} needs extraction</span>` : ""}
    </div>
    ${renderExportReadiness(selection)}
    ${renderHighSeverityConflictWarning(selection)}
    ${selection.materials.length ? `
      <table class="data-table" style="margin-top: 0.75rem;">
        <thead><tr><th>Source</th><th>Status</th></tr></thead>
        <tbody>
          ${selection.materials.map((material) => `
            <tr>
              <td>${escapeHtml(material.title)}<br><small>${escapeHtml(material.source_type)}</small></td>
              <td>
                <span class="tag ${material.extraction_status === "completed" ? "green" : "yellow"}">${escapeHtml(material.extraction_status || "not_extracted")}</span>
                <span class="tag blue">${Number(material.chunk_count || 0)} chunks</span>
                <span class="tag ${Number(material.concept_count || 0) ? "green" : "yellow"}">${Number(material.concept_count || 0)} concepts</span>
                <span class="tag green">${Number(material.verified_concept_count || 0)} verified</span>
                <span class="tag ${Number(material.rejected_concept_count || 0) ? "red" : "yellow"}">${Number(material.rejected_concept_count || 0)} rejected</span>
                <span class="tag blue">${Number(material.relationship_count || 0)} relationships</span>
                <span class="tag ${Number(material.unresolved_conflict_count || 0) ? "red" : "green"}">${Number(material.unresolved_conflict_count || 0)} conflicts</span>
                <span class="tag ${Number(material.draft_count || 0) ? "blue" : "yellow"}">${Number(material.draft_count || 0)} drafts</span>
                <span class="tag ${Number(material.verified_draft_count || 0) ? "green" : "yellow"}">${Number(material.verified_draft_count || 0)} verified drafts</span>
                <span class="tag ${Number(material.draft_warning_count || 0) ? "yellow" : "green"}">${Number(material.draft_warning_count || 0)} warnings</span>
                <span class="tag ${Number(material.ready_to_publish_draft_count || 0) ? "green" : "yellow"}">${Number(material.ready_to_publish_draft_count || 0)} ready to publish</span>
                <span class="tag ${Number(material.published_draft_count || 0) ? "green" : "yellow"}">${Number(material.published_draft_count || 0)} published</span>
                <span class="tag ${Number(material.retired_question_count || 0) ? "red" : "green"}">${Number(material.retired_question_count || 0)} retired</span>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    ` : `<p class="muted">No source materials selected.</p>`}
  `;
}


function materialRows(materials) {
  if (!materials.length) return `<p class="muted">No materials in this library yet.</p>`;
  return `
    <div class="source-selection-list">
      ${materials.map((material) => `
        <label class="source-selection-row">
          <input type="checkbox" name="source_material_ids" value="${material.id}">
          <span>
            <strong>${escapeHtml(material.title)}</strong>
            <small>${escapeHtml(material.original_filename)} · ${escapeHtml(material.source_type)}</small>
          </span>
          <span class="button-row">
            <span class="tag ${material.extraction_status === "completed" ? "green" : "yellow"}">${escapeHtml(material.extraction_status || "not_extracted")}</span>
            <span class="tag blue">${Number(material.chunk_count || 0)} chunks</span>
            <span class="tag ${Number(material.concept_count || 0) ? "green" : "yellow"}">${Number(material.concept_count || 0)} concepts</span>
            <span class="tag green">${Number(material.verified_concept_count || 0)} verified</span>
            <span class="tag ${Number(material.rejected_concept_count || 0) ? "red" : "yellow"}">${Number(material.rejected_concept_count || 0)} rejected</span>
            <span class="tag blue">${Number(material.relationship_count || 0)} relationships</span>
            <span class="tag ${Number(material.unresolved_conflict_count || 0) ? "red" : "green"}">${Number(material.unresolved_conflict_count || 0)} conflicts</span>
            <span class="tag ${Number(material.draft_count || 0) ? "blue" : "yellow"}">${Number(material.draft_count || 0)} drafts</span>
            <span class="tag ${Number(material.verified_draft_count || 0) ? "green" : "yellow"}">${Number(material.verified_draft_count || 0)} verified drafts</span>
            <span class="tag ${Number(material.draft_warning_count || 0) ? "yellow" : "green"}">${Number(material.draft_warning_count || 0)} warnings</span>
            <span class="tag ${Number(material.ready_to_publish_draft_count || 0) ? "green" : "yellow"}">${Number(material.ready_to_publish_draft_count || 0)} ready to publish</span>
            <span class="tag ${Number(material.published_draft_count || 0) ? "green" : "yellow"}">${Number(material.published_draft_count || 0)} published</span>
            <span class="tag ${Number(material.retired_question_count || 0) ? "red" : "green"}">${Number(material.retired_question_count || 0)} retired</span>
          </span>
        </label>
      `).join("")}
    </div>
  `;
}


function renderBuilderPipeline(panel, selection = { conceptExtractionActive: false, totalConcepts: 0 }) {
  if (!panel) return;
  const conceptActive = Boolean(selection.conceptExtractionActive);
  const validationActive = Number(selection.unresolvedConflictCount || 0) > 0;
  const draftingActive = Number(selection.draftCount || 0) > 0;
  panel.innerHTML = `
    ${[
      [
        "Concept Extraction",
        conceptActive ? "Active" : "Not Active",
        conceptActive ? "Concepts exist for the selected sources." : "Extract concepts from selected sources before future generation steps.",
        conceptActive ? "green" : "yellow"
      ],
      [
        "Question Drafting",
        draftingActive ? "Active" : "Not Active",
        draftingActive ? "Draft questions exist for the selected sources." : "Draft questions from selected sources when the context is ready.",
        draftingActive ? "green" : "yellow"
      ],
      [
        "Validation Queue",
        validationActive ? "Active" : "Not Active",
        validationActive ? "Unresolved conflicts are queued for review." : "Detect conflicts from source or concept detail before generation steps.",
        validationActive ? (selection.hasHighSeverityConflicts ? "red" : "yellow") : "yellow"
      ]
    ].map(([title, label, copy, tagClass]) => `
      <article class="card">
        <span class="tag ${tagClass}">${label}</span>
        <h3>${title}</h3>
        <p class="muted">${copy}</p>
      </article>
    `).join("")}
  `;
}


export function renderCourseBuilder(ctx) {
  if (!isBackendMode()) {
    renderStaticCourseBuilder(ctx);
    return;
  }

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Course Builder</h2>
        <p class="muted">Select extracted source material for future course-pack drafting.</p>
      </div>
      <div class="button-row">
        <button id="builder-open-source-library" class="button" type="button">Source Library</button>
        <button id="builder-draft-selected" class="button button-primary" type="button">Draft Questions</button>
        <button id="builder-refresh-sources" class="button" type="button">Refresh Sources</button>
      </div>
    </div>

    <section class="grid grid-2">
      <article class="card">
        <h3>Source Selection</h3>
        <div class="field">
          <label for="builder-library-select">Library</label>
          <select id="builder-library-select" class="course-select"></select>
        </div>
        <form id="builder-source-form" class="grid" style="margin-top: 0.9rem;">
          <div id="builder-materials"><p class="muted">Loading source materials...</p></div>
        </form>
      </article>
      <article id="builder-context-summary" class="card">
        <h3>Selected Context</h3>
        <p class="muted">Choose a library and select source materials.</p>
      </article>
    </section>

    <section id="builder-pipeline" class="grid grid-3" style="margin-top: 1rem;"></section>
  `;

  const librarySelect = ctx.root.querySelector("#builder-library-select");
  const materialsPanel = ctx.root.querySelector("#builder-materials");
  const form = ctx.root.querySelector("#builder-source-form");
  const summary = ctx.root.querySelector("#builder-context-summary");
  const pipeline = ctx.root.querySelector("#builder-pipeline");
  let currentMaterials = [];
  renderBuilderPipeline(pipeline);

  const updateSelection = () => {
    if (!summary || !form) return;
    const selection = buildCourseBuilderSelection(currentMaterials, selectedMaterialIdsFromFormData(new FormData(form)));
    renderSelectionSummary(summary, selection);
    renderBuilderPipeline(pipeline, selection);
  };

  const loadMaterials = async () => {
    if (!librarySelect || !materialsPanel) return;
    const libraryId = librarySelect.value;
    if (!libraryId) {
      materialsPanel.innerHTML = `<p class="muted">Create a source library before selecting sources.</p>`;
      currentMaterials = [];
      updateSelection();
      return;
    }
    currentMaterials = await attachConceptCounts(await apiGet(`/api/source-materials?library_id=${encodeURIComponent(libraryId)}`));
    materialsPanel.innerHTML = materialRows(currentMaterials);
    materialsPanel.querySelectorAll("input[name='source_material_ids']").forEach((input) => {
      input.addEventListener("change", updateSelection);
    });
    updateSelection();
  };

  const loadLibraries = async () => {
    if (!librarySelect) return;
    try {
      const libraries = await apiGet("/api/source-libraries");
      librarySelect.innerHTML = libraries.length
        ? libraries.map((library) => `<option value="${library.id}">${escapeHtml(library.name)}</option>`).join("")
        : `<option value="">No source libraries</option>`;
      await loadMaterials();
    } catch (error) {
      ctx.showStatus(`Course Builder sources failed: ${error.message}`);
    }
  };

  ctx.root.querySelector("#builder-open-source-library")?.addEventListener("click", () => ctx.navigate("sources"));
  ctx.root.querySelector("#builder-refresh-sources")?.addEventListener("click", loadLibraries);
  ctx.root.querySelector("#builder-draft-selected")?.addEventListener("click", async () => {
    if (!form) return;
    const selectedIds = selectedMaterialIdsFromFormData(new FormData(form));
    if (!selectedIds.length) {
      ctx.showStatus("Select at least one source material first.");
      return;
    }
    const selection = buildCourseBuilderSelection(currentMaterials, selectedIds);
    if (selection.hasHighSeverityConflicts) {
      ctx.showStatus("High-severity conflicts exist. Review before generating course content.");
    }
    try {
      const result = await apiPost("/api/course-builder/draft-questions", {
        course_code: ctx.bundle?.meta?.id || ctx.app.course?.id || undefined,
        source_material_ids: selectedIds
      });
      ctx.showStatus(`Created ${result.drafts_created || 0} question drafts.`);
      await loadMaterials();
    } catch (error) {
      ctx.showStatus(`Question drafting failed: ${error.message}`);
    }
  });
  librarySelect?.addEventListener("change", loadMaterials);
  loadLibraries();
}
