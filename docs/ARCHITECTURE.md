# StudyForge Architecture

StudyForge v0.6 keeps the static frontend and optional backend, then adds backend-only Source Library, concept extraction, relationship review, conflict validation, and draft-question foundations for reviewed course building.

## Frontend

- HTML/CSS/vanilla JS.
- Loads static JSON when the backend is unavailable.
- Checks `/api/admin/health` at startup.
- Requires login when the backend is available.
- Uses localStorage as the immediate UI cache.
- Syncs attempts, bookmarks, and mock exam results to the backend when authenticated.
- Shows Source Library, Concepts, Conflicts, and Question Drafts only after backend login.

## Backend

- FastAPI app in `backend/app`.
- SQLAlchemy ORM models in `backend/app/models.py`.
- SQLite database at `backend/studyforge.db` by default.
- JWT session token in an HTTP-only cookie.
- Import/export services preserve compatibility with static course packs.
- Source Library stores source libraries, source material metadata, extracted chunks, and import job status in SQLite.
- Concept extraction reads existing source chunks, stores concepts, aliases, source-concept lineage, evidence snippets, and concept relationships in SQLite.
- Concept review APIs let authenticated users review/verify/reject/restore concepts, manage aliases, view evidence, and map relationships. Merge operations preserve source lineage and reject the duplicate source concept.
- Conflict detection stores source/concept validation findings in SQLite with short evidence snippets, severity, review status, and source lineage.
- Conflict review APIs let authenticated users list/filter findings and let reviewer/admin roles resolve or reject them.
- Question drafting stores draft stems, choices, answers, plain/structured explanations, persisted validation warnings, and source/chunk/concept lineage before anything enters the live question bank.
- Draft validation checks explanation quality, duplicate-looking stems, rejected lineage, and unresolved high-severity conflicts.
- Publishing a draft is an explicit reviewer/admin action that requires no high-severity draft warnings, then creates or updates one real `Question` row while preserving draft lineage.
- Publish history and published lineage snapshots make published questions traceable and reversible without hard deletion.
- Course export can include lineage, review metadata, drafts, and retired questions by option, and export validation reports readiness warnings before download.
- Uploaded original source files are stored under `backend/data/sources/originals/` by default, outside the static frontend deployment path.
- `backend/app/ai` contains disabled provider and agent placeholders so future AI integrations can plug in without changing the Source Library data model.

## Data Flow

Static mode:

```text
data/*.json -> frontend -> localStorage
```

Backend mode:

```text
SQLite -> /api/export/{course_code} -> frontend cache -> /api/progress endpoints -> SQLite
```

Source Library:

```text
browser upload -> /api/source-materials/upload -> backend file storage + SQLite metadata
stored source -> /api/source-materials/{id}/extract -> extraction service -> source_chunks
source_chunks -> /api/source-materials/{id}/extract-concepts -> rule-based extractor -> concepts + source_concepts
concept review -> /api/concepts + /api/concept-relationships -> SQLite concepts, aliases, lineage, relationships
source/concept validation -> /api/*/detect-conflicts -> rule-based detector -> source_conflicts review queue
source/concept/course-builder drafting -> /api/*/draft-questions -> question_drafts + question_draft_lineage
draft save/review -> question validation service -> question_draft_warnings
question draft publish -> /api/question-drafts/{id}/publish -> questions + lineage_json + published_question_lineage + question_publish_history
question retire/restore -> /api/questions/{id}/* -> questions.status + question_publish_history
course export validation -> /api/export/{course_code}/validate -> export readiness warnings
```

## Design Constraint

The backend must be additive. If it is down, the current study experience still works from JSON files.

Source Library, Concepts, Conflicts, and Question Drafts are backend-only. Static mode does not upload, extract files, review extracted concepts, run validation checks, or publish generated drafts.
