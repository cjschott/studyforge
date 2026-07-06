from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    CheatSheet,
    Concept,
    Course,
    Flashcard,
    GlossaryTerm,
    Question,
    QuestionDraft,
    Source,
    SourceConflict,
)
from app.services.question_publish_service import published_lineage_to_dict, publish_history_to_dict


def question_public_id(question: Question) -> str:
    return question.legacy_id or f"q-{question.id}"


def source_tags(question: Question) -> list[str]:
    lineage = question.lineage_json or {}
    original = lineage.get("original") or {}
    return lineage.get("sourceTags") or original.get("sourceTags") or []


def question_to_static(
    question: Question,
    *,
    include_lineage: bool = True,
    include_review_metadata: bool = True,
) -> dict[str, Any]:
    lineage = question.lineage_json or {}
    original = lineage.get("original") or {}
    explanation_json = lineage.get("explanationJson") if isinstance(lineage.get("explanationJson"), dict) else None
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
    }
    if explanation_json:
        payload["explanationJson"] = explanation_json
    if include_review_metadata:
        payload["status"] = question.status
        payload["confidence"] = question.confidence
        payload["publishHistory"] = [publish_history_to_dict(row) for row in sorted(question.publish_history, key=lambda item: item.id)]
    if include_lineage:
        payload["lineage"] = lineage
        payload["publishedLineage"] = [
            published_lineage_to_dict(row) for row in sorted(question.published_lineage, key=lambda item: item.id)
        ]
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


def concept_to_export(concept: Concept) -> dict[str, Any]:
    return {
        "id": concept.id,
        "name": concept.name,
        "normalizedName": concept.normalized_name,
        "description": concept.description,
        "courseCode": concept.course_code,
        "status": concept.status,
        "confidence": concept.confidence,
        "sourceCount": len(concept.source_links),
        "relationshipCount": len(concept.relationships_a) + len(concept.relationships_b),
    }


def draft_to_export(draft: QuestionDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "courseCode": draft.course_code,
        "publishedQuestionId": draft.published_question_id,
        "questionType": draft.question_type,
        "stem": draft.stem,
        "choices": draft.choices_json,
        "correctAnswer": draft.correct_answer_json,
        "explanation": draft.explanation,
        "explanationJson": draft.explanation_json or {},
        "difficulty": draft.difficulty,
        "oaProbability": draft.oa_probability,
        "status": draft.status,
        "confidence": draft.confidence,
        "generationMethod": draft.generation_method,
    }


def export_warning(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def validate_course_export(db: Session, course_code: str) -> dict[str, Any]:
    course = db.query(Course).filter_by(course_code=course_code).one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    warnings: list[dict[str, str]] = []
    if db.query(QuestionDraft).filter_by(course_code=course.course_code, status="verified", published_question_id=None).first():
        warnings.append(
            export_warning("unpublished_verified_draft", "medium", "Course has verified drafts that have not been published.")
        )
    questions = db.query(Question).filter_by(course_id=course.id).all()
    if any(not question.published_lineage and not (question.lineage_json or {}) for question in questions):
        warnings.append(export_warning("missing_question_lineage", "high", "One or more questions are missing lineage."))
    if any(question.status == "generated" for question in questions):
        warnings.append(export_warning("generated_question", "medium", "One or more questions are still generated/unreviewed."))
    if (
        db.query(SourceConflict)
        .filter(SourceConflict.severity == "high")
        .filter(SourceConflict.status.in_(["generated", "needs_review", "reviewed"]))
        .first()
    ):
        warnings.append(
            export_warning("unresolved_high_severity_conflict", "high", "Unresolved high-severity conflicts exist.")
        )
    if (
        db.query(Question)
        .join(Concept, Question.concept_id == Concept.id)
        .filter(Question.course_id == course.id)
        .filter(Question.status != "retired")
        .filter(Concept.status == "rejected")
        .first()
    ):
        warnings.append(
            export_warning("rejected_concept_linked", "high", "Published questions are linked to rejected concepts.")
        )
    return {
        "course_code": course.course_code,
        "ready": not any(warning["severity"] == "high" for warning in warnings),
        "warnings": warnings,
    }


def export_course_pack(
    db: Session,
    course_code: str,
    *,
    include_retired: bool = False,
    include_drafts: bool = False,
    include_lineage: bool = True,
    include_review_metadata: bool = True,
) -> dict[str, Any]:
    course = db.query(Course).filter_by(course_code=course_code).one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    sources = db.query(Source).filter_by(course_id=course.id).order_by(Source.id).all()
    question_query = db.query(Question).filter_by(course_id=course.id)
    if not include_retired:
        question_query = question_query.filter(Question.status != "retired")
    questions = question_query.order_by(Question.id).all()
    flashcards = db.query(Flashcard).filter_by(course_id=course.id).order_by(Flashcard.id).all()
    glossary = db.query(GlossaryTerm).filter_by(course_id=course.id).order_by(GlossaryTerm.id).all()
    cheatsheets = db.query(CheatSheet).filter_by(course_id=course.id).order_by(CheatSheet.id).all()
    concepts = (
        db.query(Concept)
        .filter((Concept.course_id == course.id) | (Concept.course_code == course.course_code))
        .order_by(Concept.name)
        .all()
    )

    payload = {
        "course": course_meta_to_static(course),
        "meta": course_meta_to_static(course),
        "manifestEntry": {
            "id": course.course_code,
            "name": course.name,
            "shortName": course.short_name,
            "description": course.description,
            "path": f"data/{course.course_code}/",
        },
        "questions": [
            question_to_static(
                question,
                include_lineage=include_lineage,
                include_review_metadata=include_review_metadata,
            )
            for question in questions
        ],
        "concepts": [concept_to_export(concept) for concept in concepts],
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
    if include_drafts:
        payload["questionDrafts"] = [
            draft_to_export(draft)
            for draft in db.query(QuestionDraft).filter_by(course_code=course.course_code).order_by(QuestionDraft.id).all()
        ]
    return payload
