# Changelog

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
