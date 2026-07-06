import assert from "node:assert/strict";
import test from "node:test";

import {
  attachConceptCounts,
  buildCourseBuilderSelection,
  renderExportReadiness,
  renderHighSeverityConflictWarning,
  selectedMaterialIdsFromFormData
} from "./courseBuilder.js";

test("course builder parses selected source material ids from form data", () => {
  const formData = new FormData();
  formData.append("source_material_ids", "3");
  formData.append("source_material_ids", "8");
  formData.append("source_material_ids", "not-a-number");

  assert.deepEqual(selectedMaterialIdsFromFormData(formData), [3, 8]);
});

test("course builder summarizes selected source materials", () => {
  const materials = [
    {
      id: 1,
      title: "Official Objectives",
      source_type: "official_course_material",
      chunk_count: 4,
      extraction_status: "completed",
      concepts: [
        { id: 10, status: "verified", relationship_count: 2 },
        { id: 11, status: "generated", relationship_count: 1 }
      ],
      conflicts: [
        { id: 31, severity: "high", status: "needs_review" }
      ],
      drafts: [
        {
          id: 41,
          status: "needs_review",
          warnings: [{ code: "missing_lineage", severity: "high", message: "Question draft must be linked to source or concept lineage." }]
        },
        { id: 42, status: "reviewed", warnings: [] },
        { id: 44, status: "verified", warnings: [] }
      ]
    },
    { id: 2, title: "Personal Notes", source_type: "markdown", chunk_count: 0, extraction_status: "not_extracted" },
    {
      id: 3,
      title: "Practice CSV",
      source_type: "csv",
      chunk_count: 2,
      extraction_status: "completed",
      concepts: [
        { id: 11, status: "generated", relationship_count: 1 },
        { id: 12, status: "rejected", relationship_count: 0 }
      ],
      conflicts: [
        { id: 32, severity: "medium", status: "reviewed" },
        { id: 33, severity: "high", status: "resolved" }
      ],
      drafts: [
        { id: 43, status: "published", published_question_id: 88, published_question_status: "retired", warnings: [] }
      ]
    }
  ];

  const selection = buildCourseBuilderSelection(materials, [1, 3]);

  assert.deepEqual(selection.materialIds, [1, 3]);
  assert.equal(selection.totalChunks, 6);
  assert.equal(selection.totalConcepts, 3);
  assert.equal(selection.verifiedConcepts, 1);
  assert.equal(selection.rejectedConcepts, 1);
  assert.equal(selection.relationshipCount, 3);
  assert.equal(selection.unresolvedConflictCount, 2);
  assert.equal(selection.highSeverityConflictCount, 1);
  assert.equal(selection.hasHighSeverityConflicts, true);
  assert.equal(selection.draftCount, 4);
  assert.equal(selection.readyForReviewDraftCount, 1);
  assert.equal(selection.verifiedDraftCount, 1);
  assert.equal(selection.warningCount, 1);
  assert.equal(selection.readyToPublishDraftCount, 2);
  assert.equal(selection.publishedDraftCount, 1);
  assert.equal(selection.retiredQuestionCount, 1);
  assert.equal(selection.exportReady, false);
  assert.equal(selection.exportReadinessLabel, "export blocked");
  assert.equal(selection.draftLabel, "4 drafts");
  assert.equal(selection.readyForReviewDraftLabel, "1 ready for review");
  assert.equal(selection.verifiedDraftLabel, "1 verified draft");
  assert.equal(selection.warningLabel, "1 warning");
  assert.equal(selection.readyToPublishDraftLabel, "2 ready to publish");
  assert.equal(selection.publishedDraftLabel, "1 published");
  assert.equal(selection.retiredQuestionLabel, "1 retired");
  assert.equal(selection.readyCount, 2);
  assert.equal(selection.missingExtractionCount, 0);
  assert.deepEqual(selection.sourceTypes, ["csv", "official_course_material"]);
  assert.equal(selection.contextLabel, "2 sources, 6 chunks");
  assert.equal(selection.conceptLabel, "3 concepts");
  assert.equal(selection.conceptExtractionActive, true);
});

test("course builder attaches concept counts for source materials", async () => {
  const materials = [
    { id: 1, title: "Official Objectives" },
    { id: 2, title: "Personal Notes" }
  ];
  const calls = [];

  const enriched = await attachConceptCounts(materials, async (path) => {
    calls.push(path);
    if (path.includes("/1/concepts")) {
      return [
        { concept: { id: 7, name: "Firewall", status: "verified", relationship_count: 2 } },
        { concept: { id: 7, name: "Firewall", status: "verified", relationship_count: 2 } },
        { concept: { id: 8, name: "VPN", status: "rejected", relationship_count: 1 } }
      ];
    }
    if (path.includes("/api/conflicts")) {
      return [
        { id: 101, severity: "high", status: "needs_review" },
        { id: 102, severity: "low", status: "resolved" }
      ];
    }
    if (path.includes("/api/question-drafts")) {
      return [
        { id: 201, status: "reviewed", warnings: [] },
        {
          id: 202,
          status: "needs_review",
          warnings: [{ code: "missing_lineage", severity: "high", message: "Missing lineage." }]
        },
        { id: 203, status: "published", published_question_id: 89, published_question_status: "verified", warnings: [] },
        { id: 204, status: "verified", warnings: [] }
      ];
    }
    return [];
  });

  assert.deepEqual(calls, [
    "/api/source-materials/1/concepts?include_rejected=true",
    "/api/conflicts?source_id=1&include_resolved=true",
    "/api/question-drafts?source_id=1&include_rejected=true",
    "/api/source-materials/2/concepts?include_rejected=true",
    "/api/conflicts?source_id=2&include_resolved=true",
    "/api/question-drafts?source_id=2&include_rejected=true"
  ]);
  assert.equal(enriched[0].concept_count, 2);
  assert.equal(enriched[0].verified_concept_count, 1);
  assert.equal(enriched[0].rejected_concept_count, 1);
  assert.equal(enriched[0].relationship_count, 3);
  assert.equal(enriched[0].unresolved_conflict_count, 1);
  assert.equal(enriched[0].high_severity_conflict_count, 1);
  assert.equal(enriched[0].draft_count, 4);
  assert.equal(enriched[0].ready_for_review_draft_count, 1);
  assert.equal(enriched[0].verified_draft_count, 1);
  assert.equal(enriched[0].draft_warning_count, 1);
  assert.equal(enriched[0].ready_to_publish_draft_count, 2);
  assert.equal(enriched[0].published_draft_count, 1);
  assert.equal(enriched[0].retired_question_count, 0);
  assert.deepEqual(enriched[0].concept_ids, [7, 8]);
  assert.equal(enriched[1].concept_count, 0);
});

test("course builder warning renders for high-severity conflicts", () => {
  assert.match(
    renderHighSeverityConflictWarning({ hasHighSeverityConflicts: true }),
    /High-severity conflicts exist\. Review before generating course content\./
  );
  assert.equal(renderHighSeverityConflictWarning({ hasHighSeverityConflicts: false }), "");
});

test("course builder export readiness renders status and warnings", () => {
  assert.match(
    renderExportReadiness({ exportReady: false, exportReadinessLabel: "export blocked", warningCount: 2 }),
    /export blocked/
  );
  assert.match(
    renderExportReadiness({ exportReady: true, exportReadinessLabel: "export ready", warningCount: 0 }),
    /export ready/
  );
});
