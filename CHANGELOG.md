# Changelog

## v0.6.0-alpha.3

- Added publish history storage for draft publish, republish, retire, and restore actions.
- Added immutable published-question lineage snapshots so source title/type/confidence/verification metadata survives later source edits.
- Updated draft publishing to snapshot lineage, record actor/action history, block high-severity warnings, and keep idempotent published-question updates.
- Added question publish-history and lineage APIs plus restore support for retired questions.
- Hid retired questions from normal course question lists by default while keeping them visible through admin/review queries.
- Hardened course export with `include_retired`, `include_drafts`, `include_lineage`, and `include_review_metadata` options.
- Added export validation warnings for unpublished verified drafts, missing lineage, generated questions, high-severity conflicts, and rejected concepts linked to published questions.
- Improved Question Drafts, Admin Review, Administration export, and Course Builder UI surfaces for publish history, lineage, retire/restore, export options, and export readiness.

## v0.6.0-alpha.2

- Added persisted `question_draft_warnings` with structured code, severity, message, and refresh-on-save/review validation.
- Added draft validation service checks for missing stem, choices, answers, explanations, lineage, rejected linked sources/concepts, unresolved high-severity conflicts, and duplicate-looking stems.
- Added optional structured draft explanations with separate correct-answer and wrong-answer rationale while keeping plain explanation text compatible.
- Added warning APIs for `GET /api/question-drafts/{id}/warnings` and `POST /api/question-drafts/{id}/validate`.
- Hardened review flow so reviewed is allowed with warnings, reject is always allowed, and verify/publish are blocked by high-severity warnings.
- Improved Question Drafts UI with grouped warnings, high-severity filtering, lineage trust metadata, structured explanation editing, and ready-to-publish status.
- Updated Admin Review Queue draft tabs and Course Builder draft stats for warnings, ready-to-publish drafts, and published drafts.

## v0.6.0-alpha.1

- Added `question_drafts` and `question_draft_lineage` storage for draft questions, source/chunk/concept lineage, draft status, confidence, and rule-based/manual generation method.
- Added authenticated question draft APIs for list/detail/create/update, review, verify, reject, publish, source drafting, concept drafting, and Course Builder drafting.
- Added non-AI rule-based drafting from practice-question-like source chunks and reviewable concept prompts with placeholder choices.
- Added draft validation warnings for missing explanation, missing answer, missing lineage, missing wrong-answer explanations, unverified sources, and unresolved conflicts.
- Added idempotent publishing: first publish creates a real `questions` row and later publishes update that same row through the stored `published_question_id`.
- Added Question Drafts frontend screen, Admin review queue access, Source/Concept detail draft buttons, and Course Builder draft counts/action.
- Kept generated drafts out of the live question bank until an explicit human publish action.

## v0.5.0-alpha.3

- Added `source_conflicts` storage for source/concept validation findings with conflict type, severity, review status, evidence snippets, detection method, and preserved source lineage.
- Added authenticated conflict APIs for listing, filtering, reviewing, resolving, and detecting conflicts from source materials or concepts.
- Added rule-based conflict detection for legacy Security+ exam references, answer-key-like chunks, low-authority/unverified sources, missing concept lineage, duplicate-looking concepts, and verified concepts tied to weak evidence.
- Added Conflicts UI with severity/status/type/search filters, evidence detail view, source trust metadata, review/resolve/reject actions, and note capture.
- Added Source Material and Concept detail conflict detection controls with conflict counts and related conflict sections.
- Updated Course Builder selected-source stats with unresolved conflict counts and a high-severity warning before future generation steps.

## v0.5.0-alpha.2

- Added concept review action APIs for reviewed, verified, rejected, and restore workflows.
- Added concept alias list/create/delete APIs with normalized duplicate prevention.
- Added concept merge API that moves aliases, source-concept lineage, and relationships to a target concept while keeping the source concept rejected instead of hard-deleted.
- Added concept evidence API with source title, type, confidence, verification status, chunk number, page number, and evidence text.
- Added relationship update and delete APIs plus frontend controls for relationship status review.
- Improved Concepts UI with alias management, evidence display, merge controls, relationship creation/status controls, and relationship counts.
- Improved Course Builder selected-source stats with concept, verified concept, rejected concept, and relationship counts.

## v0.5.0-alpha.1

- Added authenticated concept CRUD APIs with review, verification, rejection, aliases, source lineage, and relationship endpoints.
- Added rule-based concept extraction from source chunks using headings, glossary-like lines, repeated capitalized terms, and a Security+/networking keyword seed list.
- Added concept source-link storage with evidence snippets, confidence scores, extraction method, and chunk lineage.
- Added Concepts frontend section with search, status/course filters, detail review controls, linked source evidence, and relationships.
- Added Source Material concept extraction controls and Course Builder selected-source concept counts.
- Kept LLM integration, embeddings/vector DB, and question generation disabled and out of scope.

## v0.4.0-alpha.2

- Stabilized Source Library material responses with chunk counts, extraction status, and extraction messages.
- Stopped exposing absolute backend upload paths in source material API responses.
- Added admin source-material delete cleanup for stored original files.
- Added Course Builder source selection for backend-mode source libraries and materials.
- Added selected-source context summaries for future course-pack drafting without enabling AI generation.

## v0.4.0-alpha.1

- Added Source Library foundation with authenticated source-library CRUD APIs.
- Added source material upload APIs for PDF, DOCX, TXT, Markdown, and CSV files.
- Added backend-local source file storage, SHA256 checksums, safe filename handling, duplicate upload detection, and chunk persistence.
- Added practical text extraction and 1000-1500 character chunking for AI-ready ingestion.
- Added frontend Source Library screens for library management, uploads, extraction, and chunk preview.
- Added disabled AI provider and placeholder agent modules for future local LLM integration.

## v0.3.0-alpha.2

- Improved auth/admin workflow with disabled-user handling, role changes, enable/disable controls, duplicate username validation, and password reset.
- Improved backend progress sync with review-note persistence and visible frontend sync warnings.
- Added question review workflow lists, status counts, low-confidence queues, validation-warning queues, and generated/reviewed/verified/retired actions.
- Added source lineage, status, source type, and confidence display in question explanations.
- Improved question type rendering for multi-select, matching, ordering, diagram fallback, and PBQ manual-check placeholders.
- Expanded Security+ starter pack to 50 generated/example questions, 20 flashcards, 30 glossary terms, and 5 cheat sheets.
- Improved schweb2 deployment docs, backend environment variable support, and test coverage.

## v0.3.0-alpha

- Added FastAPI backend foundation.
- Added SQLite schema for users, courses, sources, concepts, questions, flashcards, glossary, cheat sheets, attempts, bookmarks, mock sessions, and review notes.
- Added local username/password login, HTTP-only cookie sessions, and admin user management.
- Added DB-backed progress endpoints and frontend progress sync/hydration.
- Added course import/export services for legacy static course packs.
- Added question review workflow status endpoints.
- Added question type foundation for single choice, multi-select, matching, ordering, diagram, and PBQ placeholders.
- Added Security+ starter pack with generated example questions.
- Added Course Builder prompt/template foundation.
- Added deployment notes for Ubuntu, nginx, systemd, and SQLite backup.

## v0.2.0

- Added version display and app metadata.
- Added course data validation warnings in the browser console.
- Improved dashboard readiness, recommended study, continuation, high-probability, mock, and streak cards.
- Improved practice with keyboard shortcuts, missed notes, and similar-question navigation.
- Improved Mock OA with start/finish confirmations, flagged review, pass estimate, missed review, and topic recommendations.
- Improved analytics with weakest-topic sorting, high-probability accuracy, mock trends, most-missed topics, and JSON export.
- Added course pack export, import placeholder, keyboard shortcut documentation, and Course Builder placeholder.

## v0.1.0

- Initial Codex build.
- Added static HTML/CSS/vanilla JavaScript app shell.
- Added D413 course pack with dashboard, practice, mock OA, flashcards, missed review, bookmarks, search, analytics, and settings.
