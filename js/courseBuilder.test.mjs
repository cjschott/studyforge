import assert from "node:assert/strict";
import test from "node:test";

import { buildCourseBuilderSelection, selectedMaterialIdsFromFormData } from "./courseBuilder.js";

test("course builder parses selected source material ids from form data", () => {
  const formData = new FormData();
  formData.append("source_material_ids", "3");
  formData.append("source_material_ids", "8");
  formData.append("source_material_ids", "not-a-number");

  assert.deepEqual(selectedMaterialIdsFromFormData(formData), [3, 8]);
});

test("course builder summarizes selected source materials", () => {
  const materials = [
    { id: 1, title: "Official Objectives", source_type: "official_course_material", chunk_count: 4, extraction_status: "completed" },
    { id: 2, title: "Personal Notes", source_type: "markdown", chunk_count: 0, extraction_status: "not_extracted" },
    { id: 3, title: "Practice CSV", source_type: "csv", chunk_count: 2, extraction_status: "completed" }
  ];

  const selection = buildCourseBuilderSelection(materials, [1, 3]);

  assert.deepEqual(selection.materialIds, [1, 3]);
  assert.equal(selection.totalChunks, 6);
  assert.equal(selection.readyCount, 2);
  assert.equal(selection.missingExtractionCount, 0);
  assert.deepEqual(selection.sourceTypes, ["csv", "official_course_material"]);
  assert.equal(selection.contextLabel, "2 sources, 6 chunks");
});
