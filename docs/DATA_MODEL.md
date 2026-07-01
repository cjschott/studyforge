# StudyForge Data Model

Primary backend models:

- `User`: local account, role, status, password hash, login timestamps.
- `Course`: course metadata, provider, exam type, active flag, topics.
- `Source`: source metadata and confidence.
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
