import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import CheatSheet, Concept, Course, Flashcard, GlossaryTerm, Question, Source


SOURCE_TYPE_MAP = {
    "practice test": "practice_assessment",
    "official quiz": "end_quiz",
    "end-of-section quiz": "end_quiz",
    "transcript": "notes",
    "generated": "generated",
    "reddit": "reddit_emphasis",
    "standard": "standard",
    "official": "official",
}


def read_json(path: Path, fallback: Any):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def load_static_course_pack(path: str | Path) -> dict[str, Any]:
    base = Path(path).resolve()
    if not base.exists():
        raise FileNotFoundError(f"Static course folder not found: {base}")
    return {
        "course": read_json(base / "course.json", {}),
        "questions": read_json(base / "questions.json", []),
        "flashcards": read_json(base / "flashcards.json", []),
        "glossary": read_json(base / "glossary.json", []),
        "cheatsheets": read_json(base / "cheatsheets.json", []),
        "mockExams": read_json(base / "mock-exams.json", []),
        "sources": read_json(base / "sources.json", []),
    }


def normalize_source_type(value: str | None) -> str:
    lowered = str(value or "").lower()
    for key, normalized in SOURCE_TYPE_MAP.items():
        if key in lowered:
            return normalized
    return "notes"


def normalize_difficulty(value: Any) -> int:
    if isinstance(value, int):
        return min(5, max(1, value))
    text = str(value or "").strip().lower()
    mapping = {
        "very easy": 1,
        "easy": 2,
        "medium": 3,
        "moderate": 3,
        "hard": 4,
        "difficult": 4,
        "expert": 5,
    }
    return mapping.get(text, 3)


def infer_status(source_tags: list[str], source_type: str | None = None) -> str:
    combined = " ".join(source_tags + [source_type or ""]).lower()
    if "generated" in combined:
        return "generated"
    if "practice test" in combined or "practice assessment" in combined or "end-of-section quiz" in combined or "official quiz" in combined:
        return "verified"
    return "reviewed"


def infer_confidence(source_tags: list[str], source_type: str | None = None) -> int:
    combined = " ".join(source_tags + [source_type or ""]).lower()
    if "practice test" in combined or "official" in combined or "end-of-section quiz" in combined:
        return 9
    if "generated" in combined:
        return 5
    if "reddit" in combined:
        return 4
    return 7


def public_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index + 1:04d}"


def upsert_by_legacy(db: Session, model, course_id: int, legacy_id: str | None):
    if legacy_id:
        item = db.query(model).filter_by(course_id=course_id, legacy_id=legacy_id).one_or_none()
        if item:
            return item
    return model(course_id=course_id, legacy_id=legacy_id)


def source_for_question(sources: list[Source], question: dict[str, Any]) -> Source | None:
    hints = " ".join(question.get("sourceTags") or []) + " " + str(question.get("sourceType") or "")
    hints = hints.lower()
    for source in sources:
        haystack = f"{source.title} {source.source_type} {source.summary}".lower()
        if any(part and part in haystack for part in hints.split()):
            return source
    return sources[0] if sources else None


def upsert_concept(db: Session, course_id: int, term: str, topic: str = "", confidence: int = 5) -> Concept:
    concept = db.query(Concept).filter_by(course_id=course_id, name=term).one_or_none()
    if not concept:
        concept = Concept(course_id=course_id, name=term)
    concept.topic = topic or concept.topic or ""
    concept.confidence = confidence
    db.add(concept)
    return concept


def import_course_bundle(db: Session, bundle: dict[str, Any]) -> dict[str, Any]:
    meta = bundle.get("course") or bundle.get("meta") or {}
    course_code = meta.get("id") or meta.get("course_code") or meta.get("courseCode")
    if not course_code:
        raise ValueError("Course metadata must include id/course_code.")

    course = db.query(Course).filter_by(course_code=course_code).one_or_none()
    if not course:
        course = Course(course_code=course_code, name=meta.get("name") or course_code)

    course.name = meta.get("name") or course.name
    course.short_name = meta.get("shortName") or meta.get("short_name") or course.short_name or course_code.upper()
    course.description = meta.get("description") or ""
    course.version = meta.get("version") or "1.0"
    course.exam_type = meta.get("examType") or meta.get("exam_type") or "personal_study"
    course.provider = meta.get("provider") or "StudyForge"
    course.is_active = bool(meta.get("isActive", meta.get("is_active", True)))
    course.topics_json = meta.get("topics") or []
    course.legacy_mock_exams_json = bundle.get("mockExams") or bundle.get("mock_exams") or []
    db.add(course)
    db.flush()

    imported_sources: list[Source] = []
    for index, raw in enumerate(bundle.get("sources") or []):
        legacy_id = raw.get("id") or public_id(f"{course_code}-src", index)
        source = upsert_by_legacy(db, Source, course.id, legacy_id)
        source.title = raw.get("title") or legacy_id
        source.source_type = normalize_source_type(raw.get("type") or raw.get("source_type"))
        source.summary = raw.get("summary") or ""
        source.citation = raw.get("citation") or ""
        source.confidence = int(raw.get("confidence") or infer_confidence([], raw.get("type")))
        db.add(source)
        imported_sources.append(source)
    db.flush()

    concept_by_term: dict[str, Concept] = {}
    for raw in bundle.get("glossary") or []:
        term = raw.get("term")
        if term:
            concept_by_term[term.lower()] = upsert_concept(db, course.id, term, raw.get("topic") or "", int(raw.get("confidence") or 6))
    db.flush()

    for index, raw in enumerate(bundle.get("questions") or []):
        legacy_id = raw.get("id") or public_id(f"{course_code}-q", index)
        source_tags = raw.get("sourceTags") or raw.get("source_tags") or []
        source_type = raw.get("sourceType") or raw.get("source_type")
        question = upsert_by_legacy(db, Question, course.id, legacy_id)
        question.source = source_for_question(imported_sources, raw)
        question.question_type = raw.get("type") or raw.get("questionType") or raw.get("question_type") or "single_choice"
        question.topic = raw.get("topic") or ""
        question.subtopic = raw.get("subtopic") or ""
        question.difficulty = normalize_difficulty(raw.get("difficulty"))
        question.oa_probability = int(raw.get("probability") or raw.get("oa_probability") or 3)
        question.question_text = raw.get("question") or raw.get("question_text") or ""
        question.choices_json = raw.get("choices") if raw.get("choices") is not None else []
        question.answer_json = raw.get("answer") if raw.get("answer") is not None else raw.get("answer_json")
        question.explanation = raw.get("explanation") or ""
        question.why_wrong_json = raw.get("whyWrong") or raw.get("why_wrong") or raw.get("why_wrong_json") or {}
        question.memory = raw.get("memory") or ""
        question.exam_tip = raw.get("examTip") or raw.get("exam_tip") or ""
        question.status = raw.get("status") or infer_status(source_tags, source_type)
        question.confidence = int(raw.get("confidence") or infer_confidence(source_tags, source_type))
        question.lineage_json = {
            "legacyId": legacy_id,
            "sourceTags": source_tags,
            "sourceType": source_type,
            "original": raw,
        }
        concept_hint = (raw.get("concept") or raw.get("subtopic") or raw.get("topic") or "").lower()
        question.concept = concept_by_term.get(concept_hint)
        db.add(question)

    for index, raw in enumerate(bundle.get("flashcards") or []):
        legacy_id = raw.get("id") or public_id(f"{course_code}-f", index)
        card = upsert_by_legacy(db, Flashcard, course.id, legacy_id)
        card.topic = raw.get("topic") or ""
        card.front = raw.get("front") or ""
        card.back = raw.get("back") or ""
        card.memory = raw.get("memory") or ""
        card.confidence = int(raw.get("confidence") or 6)
        db.add(card)

    for raw in bundle.get("glossary") or []:
        term = raw.get("term")
        if not term:
            continue
        item = db.query(GlossaryTerm).filter_by(course_id=course.id, term=term).one_or_none()
        if not item:
            item = GlossaryTerm(course_id=course.id, term=term)
        item.topic = raw.get("topic") or ""
        item.definition = raw.get("definition") or ""
        item.exam_tip = raw.get("examTip") or raw.get("exam_tip") or ""
        item.related_terms_json = raw.get("relatedTerms") or raw.get("related_terms") or []
        item.confidence = int(raw.get("confidence") or 6)
        db.add(item)

    for index, raw in enumerate(bundle.get("cheatsheets") or bundle.get("cheatSheets") or []):
        legacy_id = raw.get("id") or public_id(f"{course_code}-cs", index)
        sheet = upsert_by_legacy(db, CheatSheet, course.id, legacy_id)
        sheet.title = raw.get("title") or legacy_id
        sheet.topic = raw.get("topic") or ""
        sheet.priority = int(raw.get("priority") or 3)
        sheet.content_json = raw.get("content") or raw.get("content_json") or []
        sheet.confidence = int(raw.get("confidence") or 6)
        db.add(sheet)

    db.commit()
    return {
        "course_id": course.id,
        "course_code": course.course_code,
        "questions": len(bundle.get("questions") or []),
        "flashcards": len(bundle.get("flashcards") or []),
        "sources": len(bundle.get("sources") or []),
    }


def import_static_course_pack(db: Session, path: str | Path) -> dict[str, Any]:
    return import_course_bundle(db, load_static_course_pack(path))
