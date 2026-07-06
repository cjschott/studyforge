import assert from "node:assert/strict";
import test from "node:test";

import {
  buildDraftPayloadFromFormData,
  filterDrafts,
  isReadyToPublish,
  publishQuestionDraft,
  renderDraftDetail,
  renderDraftList
} from "./questionDrafts.js";

const sampleDrafts = [
  {
    id: 1,
    course_code: "SY0-701",
    concept_id: 10,
    concept_name: "TLS",
    source_title: "Security+ Notes",
    question_type: "single_choice",
    stem: "What does TLS provide?",
    choices: ["Encryption", "Routing"],
    correct_answer: "Encryption",
    explanation: "TLS encrypts traffic.",
    difficulty: 2,
    oa_probability: 4,
    status: "needs_review",
    confidence: "generated",
    generation_method: "rule_based",
    explanation_json: {
      correct: "Encryption is correct because TLS encrypts traffic.",
      incorrect: {}
    },
    warnings: [
      {
        code: "missing_wrong_answer_explanations",
        severity: "medium",
        message: "Explanation does not explain why each wrong answer is wrong."
      }
    ],
    lineage: [
      {
        source_title: "Security+ Notes",
        source_type: "official_course_material",
        source_authority_level: 5,
        source_confidence: "reviewed",
        source_verification_status: "verified",
        source_chunk_number: 3,
        concept_name: "TLS",
        concept_status: "verified",
        evidence_text: "TLS encrypts traffic.",
        lineage_reason: "source_chunk"
      }
    ]
  },
  {
    id: 2,
    course_code: "D413",
    concept_id: 11,
    concept_name: "Firewall",
    stem: "Rejected draft",
    choices: [],
    correct_answer: [],
    explanation: "",
    difficulty: 3,
    oa_probability: 3,
    status: "rejected",
    confidence: "unverified",
    generation_method: "manual",
    warnings: [
      {
        code: "missing_lineage",
        severity: "high",
        message: "Question draft must be linked to source or concept lineage."
      }
    ],
    lineage: []
  },
  {
    id: 3,
    course_code: "SY0-701",
    concept_id: 12,
    concept_name: "Firewall",
    stem: "What does a firewall inspect?",
    choices: ["Packets", "Desk height"],
    correct_answer: "Packets",
    explanation: "",
    explanation_json: {
      correct: "Packets is correct because firewalls evaluate network traffic.",
      incorrect: {
        "Desk height": "Desk height is wrong because it is not network traffic."
      }
    },
    difficulty: 2,
    oa_probability: 3,
    status: "reviewed",
    confidence: "reviewed",
    generation_method: "manual",
    published_question_id: 99,
    published_question_status: "verified",
    publish_history: [
      {
        action: "published",
        previous_status: null,
        new_status: "verified",
        created_at: "2026-07-06T12:00:00Z"
      }
    ],
    warnings: [],
    lineage: []
  }
];

test("draft list renders stems statuses warnings and lineage context", () => {
  const html = renderDraftList(sampleDrafts);

  assert.match(html, /What does TLS provide\?/);
  assert.match(html, /needs_review/);
  assert.match(html, /missing_wrong_answer_explanations/);
  assert.match(html, /1 warning/);
  assert.match(html, /ready to publish/);
  assert.match(html, /Security\+ Notes/);
});

test("draft filters hide rejected by default and filter by status course concept warnings high severity and search", () => {
  assert.deepEqual(filterDrafts(sampleDrafts).map((item) => item.id), [1, 3]);
  assert.deepEqual(filterDrafts(sampleDrafts, { includeRejected: true }).map((item) => item.id), [1, 2, 3]);
  assert.deepEqual(filterDrafts(sampleDrafts, { status: "needs_review" }).map((item) => item.id), [1]);
  assert.deepEqual(filterDrafts(sampleDrafts, { courseCode: "D413", includeRejected: true }).map((item) => item.id), [2]);
  assert.deepEqual(filterDrafts(sampleDrafts, { conceptId: "10" }).map((item) => item.id), [1]);
  assert.deepEqual(filterDrafts(sampleDrafts, { warningsOnly: true, includeRejected: true }).map((item) => item.id), [1, 2]);
  assert.deepEqual(filterDrafts(sampleDrafts, { highSeverityOnly: true, includeRejected: true }).map((item) => item.id), [2]);
  assert.deepEqual(filterDrafts(sampleDrafts, { search: "routing" }).map((item) => item.id), [1]);
});

test("draft detail renders editable fields lineage validation warnings and structured explanations", () => {
  const html = renderDraftDetail(sampleDrafts[0]);

  assert.match(html, /What does TLS provide\?/);
  assert.match(html, /Encryption/);
  assert.match(html, /TLS encrypts traffic/);
  assert.match(html, /Chunk 3/);
  assert.match(html, /Authority 5/);
  assert.match(html, /verified concept/);
  assert.match(html, /source_chunk/);
  assert.match(html, /medium severity/);
  assert.match(html, /missing_wrong_answer_explanations/);
  assert.match(html, /Why correct answer is correct/);
  assert.match(html, /Why Routing is wrong/);
});

test("draft detail renders published question status and publish history", () => {
  const html = renderDraftDetail(sampleDrafts[2]);

  assert.match(html, /Published #99/);
  assert.match(html, /verified/);
  assert.match(html, /Publish History/);
  assert.match(html, /published/);
  assert.match(html, /2026-07-06T12:00:00Z/);
});

test("structured explanation editor builds expected save payload", () => {
  const formData = new FormData();
  formData.set("course_code", "SY0-701");
  formData.set("question_type", "single_choice");
  formData.set("stem", "What does TLS provide?");
  formData.set("choices", JSON.stringify(["Encryption", "Routing"]));
  formData.set("correct_answer", JSON.stringify("Encryption"));
  formData.set("explanation", "");
  formData.set("explanation_correct", "Encryption is correct because TLS protects traffic.");
  formData.set("explanation_incorrect::Routing", "Routing is wrong because TLS does not route packets.");
  formData.set("difficulty", "2");
  formData.set("oa_probability", "4");
  formData.set("status", "reviewed");
  formData.set("confidence", "reviewed");

  assert.deepEqual(buildDraftPayloadFromFormData(formData).explanation_json, {
    correct: "Encryption is correct because TLS protects traffic.",
    incorrect: {
      Routing: "Routing is wrong because TLS does not route packets."
    }
  });
});

test("ready to publish requires reviewed or verified status and no high-severity warnings", () => {
  assert.equal(isReadyToPublish(sampleDrafts[0]), false);
  assert.equal(isReadyToPublish(sampleDrafts[1]), false);
  assert.equal(isReadyToPublish(sampleDrafts[2]), true);
});

test("publish draft helper calls correct API", async () => {
  const calls = [];

  await publishQuestionDraft(7, async (path, payload) => {
    calls.push({ path, payload });
    return { id: 7, status: "published" };
  });

  assert.deepEqual(calls, [{ path: "/api/question-drafts/7/publish", payload: {} }]);
});
