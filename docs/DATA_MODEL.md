# StudyForge Data Model

Primary backend models:

- `User`: local account, role, status, password hash, login timestamps.
- `Course`: course metadata, provider, exam type, active flag, topics.
- `Source`: source metadata and confidence.
- `SourceLibrary`: named collection of uploaded source materials.
- `SourceMaterial`: uploaded source metadata, authority, verification, copyright, checksum, and backend storage path.
- `SourceChunk`: extracted text chunks with chunk number, page number when available, heading, and checksum.
- `SourceImportJob`: extraction/import status and message history per source material.
- `Concept`: normalized concepts, descriptions, review status, confidence state, optional course code, legacy course-pack compatibility fields, and aliases.
- `ConceptAlias`: alternate names for concepts with normalized aliases.
- `SourceConcept`: source-material and source-chunk lineage for extracted/manual concepts, including evidence text, confidence score, and extraction method.
- `ConceptRelationship`: typed and reviewable relationships between concepts.
- `SourceConflict`: source/concept validation findings with conflict type, severity, review status, evidence snippets, detection method, and preserved source/chunk lineage.
- `Question`: question body, type, choices, answer, explanation, workflow status, confidence, lineage.
- `Flashcard`: front/back recall cards.
- `GlossaryTerm`: definitions and exam tips.
- `CheatSheet`: structured high-yield tables.
- `QuestionAttempt`: user answer events.
- `UserCourseProgress`: summary progress per user/course.
- `UserBookmark`: saved questions.
- `MockExamSession`: completed mock exam results.
- `ReviewNote`: reviewer/student notes.

Static IDs are preserved with `legacy_id` fields where the database primary key is numeric.

Question workflow statuses:

- `generated`
- `reviewed`
- `verified`
- `retired`

Confidence ranges:

- Question confidence: `1` through `10`
- Source confidence: `1` through `10`
- Probability and difficulty: `1` through `5`
- Source material authority level: `1` through `5`

Source material enum values:

- `source_type`: `official_course_material`, `practice_assessment`, `quiz`, `vendor_doc`, `nist`, `rfc`, `community_deck`, `quizlet_csv`, `anki_apkg`, `youtube_link`, `web_link`, `personal_notes`, `csv`, `pdf`, `docx`, `markdown`, `txt`, `other`
- `confidence`: `verified`, `reviewed`, `generated`, `unverified`
- `verification_status`: `not_reviewed`, `needs_review`, `reviewed`, `verified`, `rejected`
- `copyright_status`: `owned`, `licensed`, `public`, `linked_only`, `personal_use_only`, `unknown`

Concept enum values:

- `status`: `generated`, `reviewed`, `verified`, `rejected`
- `confidence`: `generated`, `reviewed`, `verified`, `unverified`
- `extraction_method`: `manual`, `rule_based`, `ai_disabled_stub`
- `relationship_type`: `related_to`, `contrasts_with`, `depends_on`, `belongs_to`, `example_of`, `component_of`, `replaces`, `maps_to`
- `relationship.status`: `generated`, `reviewed`, `verified`, `rejected`

Concept merge behavior preserves lineage by moving `source_concepts` rows to the target concept when possible, keeping source evidence attached to chunks, and marking the merged source concept as `rejected` instead of hard-deleting it.

Source conflict enum values:

- `conflict_type`: `conflicting_definition`, `conflicting_answer`, `outdated_reference`, `unsupported_claim`, `duplicate_concept`, `low_authority_source`, `missing_lineage`, `unclear_explanation`, `possible_bad_answer`
- `severity`: `low`, `medium`, `high`
- `status`: `generated`, `needs_review`, `reviewed`, `resolved`, `rejected`
- `detection_method`: `rule_based`, `manual`, `ai_disabled_stub`

Conflict review behavior preserves lineage. Resolve and reject update review status only; no source material, chunk, concept, or source-concept link is hard-deleted.
