# StudyForge Data Model

Primary backend models:

- `User`: local account, role, status, password hash, login timestamps.
- `Course`: course metadata, provider, exam type, active flag, topics.
- `Source`: source metadata and confidence.
- `SourceLibrary`: named collection of uploaded source materials.
- `SourceMaterial`: uploaded source metadata, authority, verification, copyright, checksum, and backend storage path.
- `SourceChunk`: extracted text chunks with chunk number, page number when available, heading, and checksum.
- `SourceImportJob`: extraction/import status and message history per source material.
- `Concept`: normalized concepts and aliases.
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
