# Course Builder

The v0.5 Course Builder is a source-selection workspace, not an automated generation pipeline.

Files live under:

```text
tools/coursepack-builder/
```

The interactive frontend screen can load backend Source Libraries, list uploaded source materials, show extraction status, chunk counts, concept counts, verified/rejected concept counts, relationship counts, unresolved conflict counts, and summarize the selected source context. This context is local UI state for now; no AI job or course-pack generation job is created.

Principles:

- Official material is the source of truth.
- Quizlet is never authoritative.
- Reddit is only emphasis, not evidence.
- Generated content starts as `generated`.
- Human review is required before `reviewed` or `verified`.
- Every question needs source lineage.
- Explanations should cover correct and wrong choices.

Workflow:

1. Upload and extract source material in Source Library.
2. Open Course Builder and select the library.
3. Choose extracted source materials for the draft context.
4. Review chunk readiness and source type mix.
5. Extract concepts from source chunks in Source Material detail.
6. Review, verify, reject/restore, alias, merge, and relate concepts in Concepts.
7. Detect conflicts from source materials or concepts and resolve/reject validation findings.
8. Review Course Builder unresolved conflict counts before future generation steps.
9. Future pass: generate draft questions by type.
10. Future pass: generate supporting flashcards and glossary.
11. Future pass: validate course pack quality.
12. Future pass: human-review and update statuses.
13. Future pass: import to SQLite.
