# Course Builder

The v0.6 Course Builder is a source-selection and draft-question workspace, not an automated publishing pipeline.

Files live under:

```text
tools/coursepack-builder/
```

The interactive frontend screen can load backend Source Libraries, list uploaded source materials, show extraction status, chunk counts, concept counts, verified/rejected concept counts, relationship counts, unresolved conflict counts, draft counts, warning counts, verified draft counts, ready-to-publish counts, published counts, retired counts, export readiness, and summarize the selected source context. Users can create rule-based draft questions from selected sources. Drafts stay in review until explicitly published.

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
8. Review Course Builder unresolved conflict counts before drafting.
9. Draft questions from selected sources.
10. Review draft lineage, source authority, concept status, and validation warnings in Question Drafts.
11. Add structured correct and wrong-answer explanations.
12. Edit, review, verify, reject, or publish drafts. High-severity validation warnings block verify/publish.
13. Review publish history and published lineage snapshots.
14. Retire or restore published questions from Admin review when needed.
15. Validate and export the course pack with lineage/review metadata options.
16. Future pass: generate supporting flashcards and glossary.
17. Future pass: validate course pack quality.
