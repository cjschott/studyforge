import assert from "node:assert/strict";
import test from "node:test";

import {
  conceptStatusClass,
  extractConceptsForSource,
  filterConcepts,
  handleExtractConceptsClick,
  renderAliasList,
  renderConceptTable,
  renderEvidenceTable,
  submitRelationshipForm
} from "./concepts.js";

test("concept extraction calls the source material API", async () => {
  const calls = [];
  const result = await extractConceptsForSource(12, async (path, payload) => {
    calls.push({ path, payload });
    return { status: "completed", concepts_linked: 3 };
  });

  assert.deepEqual(calls, [{ path: "/api/source-materials/12/extract-concepts", payload: {} }]);
  assert.equal(result.concepts_linked, 3);
});

test("concept extraction click reports success and reloads", async () => {
  const statuses = [];
  let reloaded = false;

  await handleExtractConceptsClick(8, {
    apiPostFn: async () => ({ message: "Extracted 4 concept links." }),
    showStatus: (message) => statuses.push(message),
    reload: async () => {
      reloaded = true;
    }
  });

  assert.deepEqual(statuses, ["Extracted 4 concept links."]);
  assert.equal(reloaded, true);
});

test("concept list renders concepts with status confidence and source counts", () => {
  const html = renderConceptTable([
    { id: 1, name: "Firewall", status: "generated", confidence: "generated", source_count: 2, relationship_count: 3 },
    { id: 2, name: "Zero Trust", status: "verified", confidence: "verified", source_count: 1, relationship_count: 0 }
  ]);

  assert.match(html, /Firewall/);
  assert.match(html, /Zero Trust/);
  assert.match(html, /generated/);
  assert.match(html, /2 sources/);
  assert.match(html, /3 relationships/);
});

test("concept filters hide rejected by default and filter by search status and course", () => {
  const concepts = [
    { name: "Firewall", normalized_name: "firewall", status: "generated", course_code: "SECPLUS" },
    { name: "Zero Trust", normalized_name: "zero trust", status: "verified", course_code: "SECPLUS" },
    { name: "Old Term", normalized_name: "old term", status: "rejected", course_code: "NETPLUS" }
  ];

  assert.deepEqual(filterConcepts(concepts).map((concept) => concept.name), ["Firewall", "Zero Trust"]);
  assert.deepEqual(filterConcepts(concepts, { search: "zero" }).map((concept) => concept.name), ["Zero Trust"]);
  assert.deepEqual(filterConcepts(concepts, { status: "verified" }).map((concept) => concept.name), ["Zero Trust"]);
  assert.deepEqual(filterConcepts(concepts, { courseCode: "NETPLUS" }), []);
  assert.deepEqual(filterConcepts(concepts, { courseCode: "NETPLUS", includeRejected: true }).map((concept) => concept.name), ["Old Term"]);
});

test("concept status classes match review workflow states", () => {
  assert.equal(conceptStatusClass("verified"), "green");
  assert.equal(conceptStatusClass("reviewed"), "blue");
  assert.equal(conceptStatusClass("rejected"), "red");
  assert.equal(conceptStatusClass("generated"), "yellow");
});

test("aliases render with admin delete controls", () => {
  const html = renderAliasList([
    { id: 1, alias: "Packet Filter", normalized_alias: "packet filter" },
    { id: 2, alias: "Firewall Rule", normalized_alias: "firewall rule" }
  ], true);

  assert.match(html, /Packet Filter/);
  assert.match(html, /packet filter/);
  assert.match(html, /data-concept-alias-delete="1"/);
});

test("relationship form submits correct API call", async () => {
  const calls = [];
  const result = await submitRelationshipForm(5, {
    concept_b_id: "7",
    relationship_type: "depends_on",
    confidence_score: "0.75"
  }, async (path, payload) => {
    calls.push({ path, payload });
    return { id: 9 };
  });

  assert.deepEqual(calls, [{
    path: "/api/concepts/5/relationships",
    payload: {
      concept_b_id: 7,
      relationship_type: "depends_on",
      confidence_score: 0.75,
      status: "generated"
    }
  }]);
  assert.equal(result.id, 9);
});

test("evidence section renders linked chunks and source metadata", () => {
  const html = renderEvidenceTable([
    {
      source_title: "Security+ Concept Notes",
      source_type: "markdown",
      source_confidence: "reviewed",
      verification_status: "needs_review",
      chunk_number: 2,
      page_number: 4,
      heading: "VPN",
      evidence_text: "VPN evidence from an extracted chunk."
    }
  ]);

  assert.match(html, /Security\+ Concept Notes/);
  assert.match(html, /markdown/);
  assert.match(html, /reviewed/);
  assert.match(html, /needs_review/);
  assert.match(html, /Chunk 2/);
  assert.match(html, /Page 4/);
  assert.match(html, /VPN evidence/);
});
