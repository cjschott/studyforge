# StudyForge

StudyForge is a reusable, self-hosted static learning platform for course question banks. It uses plain HTML, CSS, vanilla JavaScript, JSON course packs, and browser `localStorage`.

Version: `0.2.0`

No backend, database, CDN, or build step is required.

## v0.2 Features

- Subtle app version display and `js/config.js` metadata.
- Browser-side course validation warnings in `js/validation.js`.
- Dashboard readiness helper text, recommended study, continue-where-left-off, high-probability topics, recent mock score, and local streak placeholder.
- Practice and study keyboard shortcuts.
- Missed-question notes saved per question in localStorage.
- Similar-question navigation by topic/subtopic.
- Mock OA start confirmation, final flagged/unanswered review, final submit confirmation, pass estimate, topic breakdown, missed review, and recommended next topics.
- Analytics sorted weakest-to-strongest by topic, high-probability accuracy, mock trend list, most-missed topics, and JSON summary export.
- Settings export/import for progress, current course pack export, import course-pack placeholder, and shortcut reference.
- Course Builder placeholder for future source import and generated course-pack workflow.

## Current File Tree

```text
studyforge/
├── .gitignore
├── CHANGELOG.md
├── VERSION
├── index.html
├── README.md
├── css/
│   └── style.css
├── js/
│   ├── analytics.js
│   ├── app.js
│   ├── config.js
│   ├── courses.js
│   ├── dashboard.js
│   ├── flashcards.js
│   ├── mockExam.js
│   ├── practice.js
│   ├── search.js
│   ├── storage.js
│   └── validation.js
├── data/
│   ├── courses.json
│   └── d413/
│       ├── course.json
│       ├── questions.json
│       ├── flashcards.json
│       ├── glossary.json
│       ├── cheatsheets.json
│       ├── mock-exams.json
│       └── sources.json
└── assets/
    └── images/
```

## Local Testing

Because StudyForge loads JSON with `fetch`, serve it over HTTP instead of opening `index.html` directly.

Windows PowerShell:

```powershell
python -m http.server 8080
```

Linux:

```bash
python3 -m http.server 8080
```

Open:

```text
http://127.0.0.1:8080/
```

## Nginx Deployment

Deploy under `/studyforge/`:

```bash
sudo mkdir -p /var/www/html/studyforge
sudo cp -r studyforge/* /var/www/html/studyforge/
sudo nginx -t
sudo systemctl reload nginx
```

Open:

```text
http://192.168.86.13/studyforge/
```

Deploy over the existing `/d413/` path:

```bash
sudo mkdir -p /var/www/html/d413
sudo cp -r studyforge/* /var/www/html/d413/
sudo nginx -t
sudo systemctl reload nginx
```

Open:

```text
http://192.168.86.13/d413/
```

All fetch paths are relative, so the app can be hosted from either subdirectory.

## GitHub Setup

From `E:\DevWrk\studyforge`:

```bash
git init
git add .
git commit -m "Release StudyForge v0.2"
git branch -M main
git remote add origin https://github.com/YOUR-USER/YOUR-REPO.git
git push -u origin main
```

## Add Another Course

1. Create a new folder under `data/`, for example `data/mycourse/`.
2. Add the required JSON files:
   - `course.json`
   - `questions.json`
   - `flashcards.json`
   - `glossary.json`
   - `cheatsheets.json`
   - `mock-exams.json`
   - `sources.json`
3. Register the course in `data/courses.json`:

```json
{
  "id": "mycourse",
  "name": "My Course Name",
  "shortName": "MY101",
  "description": "Short course description",
  "path": "data/mycourse/"
}
```

Keep paths relative.

## Data Schema Overview

`data/courses.json` is the manifest:

```json
[
  {
    "id": "d413",
    "name": "D413 Telecommunications & Wireless Communications",
    "shortName": "D413",
    "description": "WGU Telecommunications and Wireless Communications",
    "path": "data/d413/"
  }
]
```

`course.json` defines course metadata and topic names.

`questions.json` items should include:

```json
{
  "id": "course-q0001",
  "topic": "Multiplexing",
  "subtopic": "FDM",
  "difficulty": "Medium",
  "probability": 5,
  "sourceTags": ["Original"],
  "question": "Question text",
  "choices": ["A", "B", "C", "D"],
  "answer": "B",
  "explanation": "Why the answer is correct.",
  "memory": "Optional memory trick.",
  "examTip": "Optional exam tip."
}
```

`flashcards.json`, `glossary.json`, `cheatsheets.json`, `mock-exams.json`, and `sources.json` are optional feature data files, but each course folder should include them for consistency.

## Validation

`js/validation.js` runs after a course loads and logs warnings to the browser console for:

- Missing required question fields.
- Duplicate question IDs.
- Answers not present in choices.
- Empty topics.
- Probability values outside `1` through `5`.
- Question topics not listed in `course.json`.

Validation warnings do not stop the app.

## Progress Storage

Progress is stored only in this browser under:

```text
studyforge:v1
```

Stored data includes answered questions, missed questions, missed notes, bookmarks, review-later items, topic stats, session history, mock exam history, flashcard stats, and settings.

Use Settings to export progress JSON before:

- Clearing browser data.
- Moving to another browser or machine.
- Replacing a course pack.
- Resetting local progress.

## Backup Guidance

Use Settings for two different exports:

- `Export JSON`: backs up browser progress.
- `Export Current Course Pack`: downloads the loaded course data as one JSON bundle.

The course-pack import control is a placeholder for inspection only. A static app cannot write permanent files into `/data/`; add new course folders manually and update `data/courses.json`.
