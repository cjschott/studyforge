# Course Builder

The v0.3 Course Builder is a foundation, not an automated generation pipeline.

Files live under:

```text
tools/coursepack-builder/
```

Principles:

- Official material is the source of truth.
- Quizlet is never authoritative.
- Reddit is only emphasis, not evidence.
- Generated content starts as `generated`.
- Human review is required before `reviewed` or `verified`.
- Every question needs source lineage.
- Explanations should cover correct and wrong choices.

Workflow:

1. Extract concepts.
2. Generate draft questions by type.
3. Generate supporting flashcards and glossary.
4. Validate course pack quality.
5. Human-review and update statuses.
6. Import to SQLite.
