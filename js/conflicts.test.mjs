import assert from "node:assert/strict";
import test from "node:test";

import {
  filterConflicts,
  rejectConflict,
  renderConflictDetail,
  renderConflictList,
  resolveConflict
} from "./conflicts.js";

const sampleConflicts = [
  {
    id: 1,
    conflict_type: "outdated_reference",
    summary: "Legacy SY0-601 reference",
    evidence_a: "This chunk mentions SY0-601.",
    evidence_b: "",
    severity: "high",
    status: "needs_review",
    concept_name: "Firewall",
    source_title_a: "Security+ Notes",
    source_type_a: "markdown",
    source_authority_level_a: 4,
    source_confidence_a: "reviewed",
    source_verification_status_a: "needs_review",
    source_chunk_number_a: 2,
    source_page_number_a: 4
  },
  {
    id: 2,
    conflict_type: "low_authority_source",
    summary: "Community deck needs review",
    evidence_a: "community source",
    evidence_b: "",
    severity: "low",
    status: "resolved",
    concept_name: "VPN",
    source_title_a: "Community Deck"
  }
];

test("conflict list renders summaries severity status and linked concept", () => {
  const html = renderConflictList(sampleConflicts);

  assert.match(html, /Legacy SY0-601 reference/);
  assert.match(html, /high/);
  assert.match(html, /needs_review/);
  assert.match(html, /Firewall/);
});

test("conflict filters apply severity status type and search", () => {
  assert.deepEqual(filterConflicts(sampleConflicts).map((item) => item.id), [1]);
  assert.deepEqual(filterConflicts(sampleConflicts, { includeResolved: true }).map((item) => item.id), [1, 2]);
  assert.deepEqual(filterConflicts(sampleConflicts, { severity: "high" }).map((item) => item.id), [1]);
  assert.deepEqual(filterConflicts(sampleConflicts, { status: "resolved", includeResolved: true }).map((item) => item.id), [2]);
  assert.deepEqual(filterConflicts(sampleConflicts, { conflictType: "outdated_reference" }).map((item) => item.id), [1]);
  assert.deepEqual(filterConflicts(sampleConflicts, { search: "community", includeResolved: true }).map((item) => item.id), [2]);
});

test("conflict detail renders evidence and source metadata", () => {
  const html = renderConflictDetail(sampleConflicts[0]);

  assert.match(html, /Legacy SY0-601 reference/);
  assert.match(html, /This chunk mentions SY0-601/);
  assert.match(html, /Security\+ Notes/);
  assert.match(html, /Authority 4/);
  assert.match(html, /reviewed/);
  assert.match(html, /needs_review/);
  assert.match(html, /Chunk 2/);
  assert.match(html, /Page 4/);
});

test("resolve and reject conflict helpers call correct APIs", async () => {
  const postCalls = [];
  const putCalls = [];

  await resolveConflict(3, async (path, payload) => {
    postCalls.push({ path, payload });
    return { id: 3, status: "resolved" };
  });
  await rejectConflict(4, async (path, payload) => {
    putCalls.push({ path, payload });
    return { id: 4, status: "rejected" };
  });

  assert.deepEqual(postCalls, [{ path: "/api/conflicts/3/resolve", payload: {} }]);
  assert.deepEqual(putCalls, [{ path: "/api/conflicts/4", payload: { status: "rejected" } }]);
});
