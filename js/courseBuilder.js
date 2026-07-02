import { apiGet, isBackendMode } from "./api.js";


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
  const readyCount = selected.filter((material) => material.extraction_status === "completed" && Number(material.chunk_count || 0) > 0).length;
  const missingExtractionCount = selected.length - readyCount;
  const sourceTypes = Array.from(new Set(selected.map((material) => material.source_type).filter(Boolean))).sort();

  return {
    materialIds: selected.map((material) => Number(material.id)),
    materials: selected,
    totalChunks,
    readyCount,
    missingExtractionCount,
    sourceTypes,
    contextLabel: `${selected.length} ${selected.length === 1 ? "source" : "sources"}, ${totalChunks} ${totalChunks === 1 ? "chunk" : "chunks"}`
  };
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
      <span class="tag green">${selection.readyCount} ready</span>
      ${selection.missingExtractionCount ? `<span class="tag yellow">${selection.missingExtractionCount} needs extraction</span>` : ""}
    </div>
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
          </span>
        </label>
      `).join("")}
    </div>
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

    <section class="grid grid-3" style="margin-top: 1rem;">
      ${[
        ["Concept Extraction", "Disabled until an AI provider is configured."],
        ["Question Drafting", "Will use selected chunks and source metadata."],
        ["Validation Queue", "Future output will start as generated and require review."]
      ].map(([title, copy]) => `
        <article class="card">
          <span class="tag yellow">Not Active</span>
          <h3>${title}</h3>
          <p class="muted">${copy}</p>
        </article>
      `).join("")}
    </section>
  `;

  const librarySelect = ctx.root.querySelector("#builder-library-select");
  const materialsPanel = ctx.root.querySelector("#builder-materials");
  const form = ctx.root.querySelector("#builder-source-form");
  const summary = ctx.root.querySelector("#builder-context-summary");
  let currentMaterials = [];

  const updateSelection = () => {
    if (!summary || !form) return;
    renderSelectionSummary(summary, buildCourseBuilderSelection(currentMaterials, selectedMaterialIdsFromFormData(new FormData(form))));
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
    currentMaterials = await apiGet(`/api/source-materials?library_id=${encodeURIComponent(libraryId)}`);
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
  librarySelect?.addEventListener("change", loadMaterials);
  loadLibraries();
}
