from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import CheatSheet, Course, Flashcard, GlossaryTerm, Question, Source


def question_public_id(question: Question) -> str:
    return question.legacy_id or f"q-{question.id}"


def source_tags(question: Question) -> list[str]:
    lineage = question.lineage_json or {}
    original = lineage.get("original") or {}
    return lineage.get("sourceTags") or original.get("sourceTags") or []


def question_to_static(question: Question) -> dict[str, Any]:
    lineage = question.lineage_json or {}
    original = lineage.get("original") or {}
    payload = {
        "id": question_public_id(question),
        "type": question.question_type,
        "questionType": question.question_type,
        "topic": question.topic,
        "subtopic": question.subtopic,
        "difficulty": original.get("difficulty", question.difficulty),
        "probability": question.oa_probability,
        "sourceTags": source_tags(question),
        "sourceType": original.get("sourceType") or lineage.get("sourceType") or "",
        "question": question.question_text,
        "choices": question.choices_json,
        "answer": question.answer_json,
        "explanation": question.explanation,
        "whyWrong": question.why_wrong_json,
        "memory": question.memory,
        "examTip": question.exam_tip,
        "status": question.status,
        "confidence": question.confidence,
        "lineage": lineage,
    }
    if "image" in original:
        payload["image"] = original["image"]
    if "scenario" in original:
        payload["scenario"] = original["scenario"]
    if "task" in original:
        payload["task"] = original["task"]
    return payload


def course_meta_to_static(course: Course) -> dict[str, Any]:
    return {
        "id": course.course_code,
        "name": course.name,
        "shortName": course.short_name,
        "version": course.version,
        "description": course.description,
        "examType": course.exam_type,
        "provider": course.provider,
        "topics": course.topics_json or [],
    }


def export_course_pack(db: Session, course_code: str) -> dict[str, Any]:
    course = db.query(Course).filter_by(course_code=course_code).one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    sources = db.query(Source).filter_by(course_id=course.id).order_by(Source.id).all()
    questions = db.query(Question).filter_by(course_id=course.id).order_by(Question.id).all()
    flashcards = db.query(Flashcard).filter_by(course_id=course.id).order_by(Flashcard.id).all()
    glossary = db.query(GlossaryTerm).filter_by(course_id=course.id).order_by(GlossaryTerm.id).all()
    cheatsheets = db.query(CheatSheet).filter_by(course_id=course.id).order_by(CheatSheet.id).all()

    return {
        "course": course_meta_to_static(course),
        "meta": course_meta_to_static(course),
        "manifestEntry": {
            "id": course.course_code,
            "name": course.name,
            "shortName": course.short_name,
            "description": course.description,
            "path": f"data/{course.course_code}/",
        },
        "questions": [question_to_static(question) for question in questions],
        "flashcards": [
            {
                "id": card.legacy_id or f"f-{card.id}",
                "topic": card.topic,
                "front": card.front,
                "back": card.back,
                "memory": card.memory,
                "confidence": card.confidence,
            }
            for card in flashcards
        ],
        "glossary": [
            {
                "term": term.term,
                "topic": term.topic,
                "definition": term.definition,
                "examTip": term.exam_tip,
                "relatedTerms": term.related_terms_json,
                "confidence": term.confidence,
            }
            for term in glossary
        ],
        "cheatsheets": [
            {
                "id": sheet.legacy_id or f"cs-{sheet.id}",
                "title": sheet.title,
                "topic": sheet.topic,
                "priority": sheet.priority,
                "content": sheet.content_json,
                "confidence": sheet.confidence,
            }
            for sheet in cheatsheets
        ],
        "mockExams": course.legacy_mock_exams_json or [],
        "sources": [
            {
                "id": source.legacy_id or f"src-{source.id}",
                "title": source.title,
                "type": source.source_type,
                "summary": source.summary,
                "citation": source.citation,
                "confidence": source.confidence,
            }
            for source in sources
        ],
    }
