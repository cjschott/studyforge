import { apiDelete, apiFetch, apiGet, apiPost, apiPut, isBackendMode } from "./api.js";
import { handleExtractConceptsClick, renderSourceConceptSummary } from "./concepts.js";
import { renderConflictList } from "./conflicts.js";


const SOURCE_TYPES = [
  "official_course_material",
  "practice_assessment",
  "quiz",
  "vendor_doc",
  "nist",
  "rfc",
  "community_deck",
  "quizlet_csv",
  "anki_apkg",
  "youtube_link",
  "web_link",
  "personal_notes",
  "csv",
  "pdf",
  "docx",
  "markdown",
  "txt",
  "other"
];
const CONFIDENCE_VALUES = ["verified", "reviewed", "generated", "unverified"];
const VERIFICATION_VALUES = ["not_reviewed", "needs_review", "reviewed", "verified", "rejected"];
const COPYRIGHT_VALUES = ["owned", "licensed", "public", "linked_only", "personal_use_only", "unknown"];


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


function emptyMessage(message) {
  return `<section class="empty-state"><h2>${escapeHtml(message)}</h2></section>`;
}


export function buildSourceUploadFormData(fields, file) {
  const formData = new FormData();
  formData.append("library_id", String(fields.libraryId));
  formData.append("title", fields.title || "");
  formData.append("source_type", fields.sourceType || "other");
  formData.append("authority_level", String(fields.authorityLevel || 3));
  formData.append("confidence", fields.confidence || "unverified");
  formData.append("verification_status", fields.verificationStatus || "not_reviewed");
  formData.append("copyright_status", fields.copyrightStatus || "unknown");
  formData.append("original_url", fields.originalUrl || "");
  formData.append("file", file);
  return formData;
}


export function uploadSourceMaterial(fields, file, apiFetchFn = apiFetch) {
  return apiFetchFn("/api/source-materials/upload", {
    method: "POST",
    body: buildSourceUploadFormData(fields, file)
  });
}


export function sourceMaterialStatusSummary(material) {
  const status = material.extraction_status || "not_extracted";
  const chunks = Number(material.chunk_count || 0);
  return {
    status,
    chunkLabel: `${chunks} ${chunks === 1 ? "chunk" : "chunks"}`,
    statusClass: status === "completed" && chunks > 0 ? "green" : "yellow"
  };
}


async function renderLibraryList(ctx) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Source Library</h2>
        <p class="muted">Manage source collections and uploaded source material.</p>
      </div>
      <button id="source-refresh" class="button" type="button">Refresh</button>
    </div>

    <section class="grid grid-2">
      <article class="card">
        <h3>Create Library</h3>
        <form id="source-library-create" class="grid">
          <div class="field">
            <label for="source-library-name">Name</label>
            <input id="source-library-name" class="input" name="name" required>
          </div>
          <div class="field">
            <label for="source-library-category">Category</label>
            <input id="source-library-category" class="input" name="category">
          </div>
          <div class="field">
            <label for="source-library-description">Description</label>
            <textarea id="source-library-description" class="textarea" name="description"></textarea>
          </div>
          <button class="button button-primary" type="submit">Create Library</button>
        </form>
      </article>
      <article class="card">
        <h3>Libraries</h3>
        <div id="source-library-list"><p class="muted">Loading libraries...</p></div>
      </article>
    </section>
  `;

  const listLibraries = async () => {
    const panel = ctx.root.querySelector("#source-library-list");
    if (!panel) return;
    try {
      const libraries = await apiGet("/api/source-libraries");
      panel.innerHTML = libraries.length ? `
        <table class="data-table">
          <thead><tr><th>Name</th><th>Category</th><th>Actions</th></tr></thead>
          <tbody>
            ${libraries.map((library) => `
              <tr>
                <td>${escapeHtml(library.name)}<br><small>${escapeHtml(library.description)}</small></td>
                <td>${escapeHtml(library.category || "")}</td>
                <td>
                  <div class="button-row">
                    <button class="button" data-source-library-open="${library.id}" type="button">Open</button>
                    ${ctx.app.user?.role === "admin" ? `<button class="button button-danger" data-source-library-delete="${library.id}" type="button">Delete</button>` : ""}
                  </div>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      ` : `<p class="muted">No source libraries yet.</p>`;

      panel.querySelectorAll("[data-source-library-open]").forEach((button) => {
        button.addEventListener("click", () => ctx.navigate("sources", { libraryId: button.dataset.sourceLibraryOpen }));
      });
      panel.querySelectorAll("[data-source-library-delete]").forEach((button) => {
        button.addEventListener("click", async () => {
          if (!confirm("Delete this source library and its materials?")) return;
          try {
            await apiDelete(`/api/source-libraries/${button.dataset.sourceLibraryDelete}`);
            ctx.showStatus("Source library deleted.");
            await listLibraries();
          } catch (error) {
            ctx.showStatus(`Delete failed: ${error.message}`);
          }
        });
      });
    } catch (error) {
      ctx.showStatus(`Source libraries failed: ${error.message}`);
    }
  };

  ctx.root.querySelector("#source-refresh")?.addEventListener("click", listLibraries);
  ctx.root.querySelector("#source-library-create")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const library = await apiPost("/api/source-libraries", {
        name: String(data.get("name") || ""),
        description: String(data.get("description") || ""),
        category: String(data.get("category") || "")
      });
      form.reset();
      ctx.showStatus("Source library created.");
      ctx.navigate("sources", { libraryId: String(library.id) });
    } catch (error) {
      ctx.showStatus(`Create library failed: ${error.message}`);
    }
  });

  await listLibraries();
}


async function renderLibraryDetail(ctx, libraryId) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Source Library</h2>
        <p class="muted">Loading library...</p>
      </div>
      <button id="source-back" class="button" type="button">All Libraries</button>
    </div>
    <section id="source-library-detail"><p class="muted">Loading source library...</p></section>
  `;
  ctx.root.querySelector("#source-back")?.addEventListener("click", () => ctx.navigate("sources"));

  try {
    const [library, materials] = await Promise.all([
      apiGet(`/api/source-libraries/${libraryId}`),
      apiGet(`/api/source-materials?library_id=${libraryId}`)
    ]);
    const panel = ctx.root.querySelector("#source-library-detail");
    if (!panel) return;
    panel.innerHTML = `
      <section class="grid grid-2">
        <article class="card">
          <h3>${escapeHtml(library.name)}</h3>
          <form id="source-library-edit" class="grid">
            <div class="field">
              <label for="source-edit-name">Name</label>
              <input id="source-edit-name" class="input" name="name" value="${escapeHtml(library.name)}" required>
            </div>
            <div class="field">
              <label for="source-edit-category">Category</label>
              <input id="source-edit-category" class="input" name="category" value="${escapeHtml(library.category || "")}">
            </div>
            <div class="field">
              <label for="source-edit-description">Description</label>
              <textarea id="source-edit-description" class="textarea" name="description">${escapeHtml(library.description || "")}</textarea>
            </div>
            <button class="button button-primary" type="submit">Save Library</button>
          </form>
        </article>
        <article class="card">
          <h3>Upload Source</h3>
          <form id="source-upload-form" class="grid">
            <div class="field">
              <label for="source-upload-title">Title</label>
              <input id="source-upload-title" class="input" name="title" required>
            </div>
            <div class="field">
              <label for="source-upload-file">File</label>
              <input id="source-upload-file" class="input" name="file" type="file" accept=".pdf,.docx,.txt,.md,.markdown,.csv" required>
            </div>
            <div class="grid grid-2">
              <div class="field">
                <label for="source-upload-type">Source type</label>
                <select id="source-upload-type" class="course-select" name="source_type">${optionList(SOURCE_TYPES, "personal_notes")}</select>
              </div>
              <div class="field">
                <label for="source-upload-authority">Authority</label>
                <select id="source-upload-authority" class="course-select" name="authority_level">${[1, 2, 3, 4, 5].map((value) => `<option value="${value}" ${value === 3 ? "selected" : ""}>${value}</option>`).join("")}</select>
              </div>
            </div>
            <div class="grid grid-3">
              <div class="field">
                <label for="source-upload-confidence">Confidence</label>
                <select id="source-upload-confidence" class="course-select" name="confidence">${optionList(CONFIDENCE_VALUES, "unverified")}</select>
              </div>
              <div class="field">
                <label for="source-upload-verification">Verification</label>
                <select id="source-upload-verification" class="course-select" name="verification_status">${optionList(VERIFICATION_VALUES, "not_reviewed")}</select>
              </div>
              <div class="field">
                <label for="source-upload-copyright">Copyright</label>
                <select id="source-upload-copyright" class="course-select" name="copyright_status">${optionList(COPYRIGHT_VALUES, "unknown")}</select>
              </div>
            </div>
            <div class="field">
              <label for="source-upload-url">Original URL</label>
              <input id="source-upload-url" class="input" name="original_url" type="url">
            </div>
            <button class="button button-primary" type="submit">Upload Source</button>
          </form>
        </article>
      </section>

      <section class="card" style="margin-top: 1rem;">
        <h3>Materials</h3>
        ${materials.length ? `
          <table class="data-table">
            <thead><tr><th>Title</th><th>Metadata</th><th>Actions</th></tr></thead>
            <tbody>
              ${materials.map((material) => {
                const status = sourceMaterialStatusSummary(material);
                return `
                <tr>
                  <td>${escapeHtml(material.title)}<br><small>${escapeHtml(material.original_filename)}</small></td>
                  <td>
                    <span class="tag blue">${escapeHtml(material.source_type)}</span>
                    <span class="tag yellow">Authority ${material.authority_level}</span>
                    <span class="tag">${escapeHtml(material.confidence)}</span>
                    <span class="tag ${status.statusClass}">${escapeHtml(status.status)}</span>
                    <span class="tag blue">${escapeHtml(status.chunkLabel)}</span>
                  </td>
                  <td><button class="button" data-source-material-open="${material.id}" type="button">Open</button></td>
                </tr>
              `; }).join("")}
            </tbody>
          </table>
        ` : `<p class="muted">No materials in this library yet.</p>`}
      </section>
    `;

    panel.querySelector("#source-library-edit")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      try {
        await apiPut(`/api/source-libraries/${libraryId}`, {
          name: String(data.get("name") || ""),
          description: String(data.get("description") || ""),
          category: String(data.get("category") || "")
        });
        ctx.showStatus("Source library saved.");
        await renderLibraryDetail(ctx, libraryId);
      } catch (error) {
        ctx.showStatus(`Save library failed: ${error.message}`);
      }
    });

    panel.querySelector("#source-upload-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const data = new FormData(form);
      const file = data.get("file");
      if (!(file instanceof File) || !file.name) {
        ctx.showStatus("Upload failed: choose a source file.");
        return;
      }
      try {
        await uploadSourceMaterial({
          libraryId,
          title: String(data.get("title") || ""),
          sourceType: String(data.get("source_type") || "other"),
          authorityLevel: Number(data.get("authority_level") || 3),
          confidence: String(data.get("confidence") || "unverified"),
          verificationStatus: String(data.get("verification_status") || "not_reviewed"),
          copyrightStatus: String(data.get("copyright_status") || "unknown"),
          originalUrl: String(data.get("original_url") || "")
        }, file);
        form.reset();
        ctx.showStatus("Source material uploaded.");
        await renderLibraryDetail(ctx, libraryId);
      } catch (error) {
        ctx.showStatus(`Upload failed: ${error.message}`);
      }
    });

    panel.querySelectorAll("[data-source-material-open]").forEach((button) => {
      button.addEventListener("click", () => {
        ctx.navigate("sources", { libraryId: String(libraryId), materialId: button.dataset.sourceMaterialOpen });
      });
    });
  } catch (error) {
    ctx.showStatus(`Source library failed: ${error.message}`);
  }
}


async function renderMaterialDetail(ctx, libraryId, materialId) {
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Source Material</h2>
        <p class="muted">Loading material...</p>
      </div>
      <button id="source-library-back" class="button" type="button">Back to Library</button>
    </div>
    <section id="source-material-detail"><p class="muted">Loading source material...</p></section>
  `;
  ctx.root.querySelector("#source-library-back")?.addEventListener("click", () => ctx.navigate("sources", { libraryId }));

  const loadMaterial = async () => {
    const [material, chunks, conceptLinks, conflicts] = await Promise.all([
      apiGet(`/api/source-materials/${materialId}`),
      apiGet(`/api/source-materials/${materialId}/chunks`),
      apiGet(`/api/source-materials/${materialId}/concepts`),
      apiGet(`/api/conflicts?source_id=${materialId}&include_resolved=true`)
    ]);
    const panel = ctx.root.querySelector("#source-material-detail");
    if (!panel) return;
    const unresolvedConflicts = conflicts.filter((conflict) => !["resolved", "rejected"].includes(conflict.status));
    panel.innerHTML = `
      <section class="grid grid-2">
        <article class="card">
          <h3>${escapeHtml(material.title)}</h3>
          <table class="data-table">
            <tbody>
              <tr><th>Filename</th><td>${escapeHtml(material.original_filename)}</td></tr>
              <tr><th>Source type</th><td>${escapeHtml(material.source_type)}</td></tr>
              <tr><th>Authority</th><td>${material.authority_level}</td></tr>
              <tr><th>Confidence</th><td>${escapeHtml(material.confidence)}</td></tr>
              <tr><th>Verification</th><td>${escapeHtml(material.verification_status)}</td></tr>
              <tr><th>Copyright</th><td>${escapeHtml(material.copyright_status)}</td></tr>
              <tr><th>Checksum</th><td><code>${escapeHtml(material.checksum)}</code></td></tr>
              ${material.original_url ? `<tr><th>Original URL</th><td><a href="${escapeHtml(material.original_url)}" target="_blank" rel="noreferrer">${escapeHtml(material.original_url)}</a></td></tr>` : ""}
            </tbody>
          </table>
        </article>
        <article class="card">
          <h3>Extraction</h3>
          <span class="tag ${chunks.length ? "green" : "yellow"}">${chunks.length ? "extracted" : "not_reviewed"}</span>
          <p class="muted">${chunks.length} chunks available.</p>
          <div class="button-row">
            <button id="source-run-extract" class="button button-primary" type="button">Extract Chunks</button>
            <button id="source-run-concept-extract" class="button" type="button" ${chunks.length ? "" : "disabled"}>Extract Concepts</button>
            <button id="source-run-conflict-detect" class="button" type="button" ${chunks.length ? "" : "disabled"}>Detect Conflicts</button>
          </div>
          <div class="button-row" style="margin-top: 0.9rem;">
            <span class="tag ${conflicts.length ? "yellow" : "green"}">${conflicts.length} conflicts</span>
            <span class="tag ${unresolvedConflicts.length ? "red" : "green"}">${unresolvedConflicts.length} unresolved</span>
          </div>
        </article>
      </section>
      <section class="card" style="margin-top: 1rem;">
        <h3>Concepts Found</h3>
        ${renderSourceConceptSummary(conceptLinks)}
      </section>
      <section class="card" style="margin-top: 1rem;">
        <h3>Conflicts</h3>
        ${renderConflictList(conflicts)}
      </section>
      <section class="card" style="margin-top: 1rem;">
        <h3>Chunks</h3>
        ${chunks.length ? chunks.map((chunk) => `
          <article class="chunk-preview">
            <div class="button-row">
              <span class="tag blue">Chunk ${chunk.chunk_number}</span>
              ${chunk.page_number ? `<span class="tag">Page ${chunk.page_number}</span>` : ""}
              ${chunk.heading ? `<span class="tag yellow">${escapeHtml(chunk.heading)}</span>` : ""}
            </div>
            <p>${escapeHtml(chunk.text.slice(0, 900))}${chunk.text.length > 900 ? "..." : ""}</p>
          </article>
        `).join("") : `<p class="muted">No chunks extracted yet.</p>`}
      </section>
    `;

    panel.querySelector("#source-run-extract")?.addEventListener("click", async () => {
      try {
        const result = await apiPost(`/api/source-materials/${materialId}/extract`, {});
        ctx.showStatus(result.message || "Extraction completed.");
        await loadMaterial();
      } catch (error) {
        ctx.showStatus(`Extraction failed: ${error.message}`);
      }
    });

    panel.querySelector("#source-run-concept-extract")?.addEventListener("click", async () => {
      try {
        await handleExtractConceptsClick(materialId, {
          showStatus: ctx.showStatus,
          reload: loadMaterial
        });
      } catch (error) {
        ctx.showStatus(`Concept extraction failed: ${error.message}`);
      }
    });

    panel.querySelector("#source-run-conflict-detect")?.addEventListener("click", async () => {
      try {
        const result = await apiPost(`/api/source-materials/${materialId}/detect-conflicts`, {});
        ctx.showStatus(result.message || "Conflict detection completed.");
        await loadMaterial();
      } catch (error) {
        ctx.showStatus(`Conflict detection failed: ${error.message}`);
      }
    });

    panel.querySelectorAll("[data-conflict-open]").forEach((button) => {
      button.addEventListener("click", () => ctx.navigate("conflicts", { conflictId: button.dataset.conflictOpen }));
    });
  };

  try {
    await loadMaterial();
  } catch (error) {
    ctx.showStatus(`Source material failed: ${error.message}`);
  }
}


export function renderSourceLibrary(ctx) {
  if (!isBackendMode()) {
    ctx.root.innerHTML = emptyMessage("Backend login required for Source Library.");
    return;
  }

  const libraryId = ctx.params.libraryId;
  const materialId = ctx.params.materialId;
  if (libraryId && materialId) {
    renderMaterialDetail(ctx, libraryId, materialId);
    return;
  }
  if (libraryId) {
    renderLibraryDetail(ctx, libraryId);
    return;
  }
  renderLibraryList(ctx);
}
