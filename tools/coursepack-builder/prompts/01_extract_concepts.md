# Extract Concepts

Given trusted course source material, extract concepts as structured JSON.

Return:

- `name`
- `topic`
- `subtopic`
- `aliases`
- `relatedConcepts`
- `confidence`
- `sourceLineage`

Do not invent facts. If a concept is only inferred, set lower confidence and explain the source gap.
