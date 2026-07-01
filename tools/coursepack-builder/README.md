# StudyForge Course Pack Builder

This folder holds reusable prompts, templates, and examples for building StudyForge course packs.

Quality rules:

- Official material is the source of truth.
- Quizlet is never authoritative.
- Reddit can indicate emphasis, but it must not be treated as factual source material.
- Generated questions start as `generated`, then move to `reviewed`, then `verified`.
- Questions must not reveal the answer in the stem.
- Every question needs source lineage.
- Explanations should explain why the correct answer is correct and why wrong answers are wrong.

Recommended workflow:

1. Collect source material and source metadata.
2. Extract concepts and aliases.
3. Generate draft questions by type.
4. Validate question quality.
5. Human-review each question before marking it reviewed or verified.
6. Import the pack into SQLite with the backend importer.
