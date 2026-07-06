import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Concept,
    Course,
    Question,
    QuestionDraft,
    QuestionDraftLineage,
    SourceChunk,
    SourceConcept,
    SourceMaterial,
)
from app.services.question_validation_service import refresh_question_draft_warnings, stored_warnings_for_draft
from app.services.question_publish_service import record_publish_history, replace_published_lineage_snapshot


CHOICE_PATTERN = re.compile(r"^\s*([A-H])[\.)]\s+(.+?)\s*$", re.IGNORECASE)
ANSWER_PATTERN = re.compile(r"\b(?:answer|correct answer|correct)\s*:\s*([A-H]|.+)", re.IGNORECASE)
QUESTION_PREFIX_PATTERN = re.compile(r"^\s*(?:question|q)\s*:\s*(.+)", re.IGNORECASE)
EXPLANATION_PATTERN = re.compile(r"\bexplanation\s*:\s*(.+)", re.IGNORECASE | re.DOTALL)


def evidence_snippet(text: str, limit: int = 500) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    return compact[:limit]


def get_course_or_404(db: Session, course_code: str) -> Course:
    course = db.query(Course).filter_by(course_code=course_code).one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


def normalize_course_code(db: Session, requested: str | None, concept: Concept | None = None) -> str:
    requested_code = str(requested or "").strip()
    if requested_code:
        return requested_code
    concept_code = str(concept.course_code or "").strip() if concept else ""
    if concept_code:
        return concept_code
    course = db.query(Course).order_by(Course.id).first()
    return course.course_code if course else "GENERAL"


def parse_practice_question(text: str) -> dict[str, Any] | None:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return None

    stem = ""
    choices_by_letter: dict[str, str] = {}
    answer_token = ""
    explanation = ""

    for line in lines:
        choice_match = CHOICE_PATTERN.match(line)
        if choice_match:
            choices_by_letter[choice_match.group(1).upper()] = choice_match.group(2).strip()
            continue
        answer_match = ANSWER_PATTERN.search(line)
        if answer_match:
            answer_token = answer_match.group(1).strip()
            continue
        explanation_match = EXPLANATION_PATTERN.search(line)
        if explanation_match:
            explanation = explanation_match.group(1).strip()
            continue
        prefix_match = QUESTION_PREFIX_PATTERN.match(line)
        if prefix_match:
            stem = prefix_match.group(1).strip()
        elif not stem and "?" in line:
            stem = line.strip()

    if not stem and not choices_by_letter:
        return None
    choices = [choices_by_letter[key] for key in sorted(choices_by_letter)]
    correct_answer: Any = []
    if answer_token:
        letter = answer_token.strip().upper().rstrip(".")
        correct_answer = choices_by_letter.get(letter, answer_token.strip())
    return {
        "stem": stem or "Which statement is best supported by this source chunk?",
        "choices": choices,
        "correct_answer": correct_answer,
        "explanation": explanation,
    }


def placeholder_choices(concept_name: str | None = None) -> list[str]:
    subject = concept_name or "this source"
    return [
        f"Needs review: correct description for {subject}",
        "Needs review: plausible distractor",
        "Needs review: plausible distractor",
        "Needs review: plausible distractor",
    ]


def add_lineage_rows(db: Session, draft: QuestionDraft, rows: list[dict[str, Any]]):
    for row in rows:
        db.add(
            QuestionDraftLineage(
                draft_id=draft.id,
                source_id=row.get("source_id"),
                source_chunk_id=row.get("source_chunk_id"),
                concept_id=row.get("concept_id"),
                evidence_text=evidence_snippet(row.get("evidence_text", "")),
                lineage_reason=row.get("lineage_reason") or "manual",
            )
        )


def default_lineage_for_draft(db: Session, draft: QuestionDraft) -> list[dict[str, Any]]:
    if not any([draft.source_id, draft.source_chunk_id, draft.concept_id]):
        return []
    source_id = draft.source_id
    evidence = ""
    if draft.source_chunk_id:
        chunk = db.get(SourceChunk, draft.source_chunk_id)
        if chunk:
            source_id = source_id or chunk.source_id
            evidence = chunk.text
    return [
        {
            "source_id": source_id,
            "source_chunk_id": draft.source_chunk_id,
            "concept_id": draft.concept_id,
            "evidence_text": evidence,
            "lineage_reason": "manual",
        }
    ]


def create_question_draft(
    db: Session,
    *,
    course_code: str,
    created_by: int,
    stem: str,
    source_id: int | None = None,
    source_chunk_id: int | None = None,
    concept_id: int | None = None,
    question_type: str = "single_choice",
    choices: Any = None,
    correct_answer: Any = None,
    explanation: str = "",
    explanation_json: dict[str, Any] | None = None,
    difficulty: int = 3,
    oa_probability: int = 3,
    status_value: str = "needs_review",
    confidence: str = "generated",
    generation_method: str = "manual",
    lineage: list[dict[str, Any]] | None = None,
) -> QuestionDraft:
    draft = QuestionDraft(
        course_code=course_code,
        source_id=source_id,
        source_chunk_id=source_chunk_id,
        concept_id=concept_id,
        question_type=question_type,
        stem=stem,
        choices_json=choices if choices is not None else [],
        correct_answer_json=correct_answer if correct_answer is not None else [],
        explanation=explanation or "",
        explanation_json=explanation_json or {},
        difficulty=difficulty,
        oa_probability=oa_probability,
        status=status_value,
        confidence=confidence,
        generation_method=generation_method,
        created_by=created_by,
    )
    db.add(draft)
    db.flush()
    rows = lineage if lineage is not None else default_lineage_for_draft(db, draft)
    add_lineage_rows(db, draft, rows)
    db.flush()
    refresh_question_draft_warnings(db, draft)
    db.commit()
    db.refresh(draft)
    return draft


def draft_warnings(db: Session, draft: QuestionDraft) -> list[dict[str, Any]]:
    if not draft.warnings:
        refresh_question_draft_warnings(db, draft)
    return stored_warnings_for_draft(draft)


def draft_status(draft: QuestionDraft, next_status: str, confidence: str | None = None) -> QuestionDraft:
    draft.status = next_status
    if confidence:
        draft.confidence = confidence
    return draft


def source_lineage(chunk: SourceChunk, concept_id: int | None = None, reason: str = "source_chunk") -> list[dict[str, Any]]:
    return [
        {
            "source_id": chunk.source_id,
            "source_chunk_id": chunk.id,
            "concept_id": concept_id,
            "evidence_text": chunk.text,
            "lineage_reason": reason,
        }
    ]


def draft_from_source_chunk(db: Session, chunk: SourceChunk, course_code: str, user_id: int) -> QuestionDraft:
    parsed = parse_practice_question(chunk.text)
    if parsed:
        stem = parsed["stem"]
        choices = parsed["choices"] or placeholder_choices()
        correct_answer = parsed["correct_answer"]
        explanation = parsed["explanation"]
    else:
        stem = f"Which statement is best supported by {chunk.heading}?" if chunk.heading else "Which statement is best supported by this source chunk?"
        choices = placeholder_choices()
        correct_answer = []
        explanation = ""
    return create_question_draft(
        db,
        course_code=course_code,
        created_by=user_id,
        source_id=chunk.source_id,
        source_chunk_id=chunk.id,
        stem=stem,
        choices=choices,
        correct_answer=correct_answer,
        explanation=explanation,
        generation_method="rule_based",
        lineage=source_lineage(chunk),
    )


def draft_questions_for_source(db: Session, material: SourceMaterial, course_code: str, user_id: int, limit: int = 10) -> list[QuestionDraft]:
    chunks = db.query(SourceChunk).filter_by(source_id=material.id).order_by(SourceChunk.chunk_number).limit(limit).all()
    return [draft_from_source_chunk(db, chunk, course_code, user_id) for chunk in chunks]


def draft_questions_for_concept(db: Session, concept: Concept, course_code: str, user_id: int) -> list[QuestionDraft]:
    link = db.query(SourceConcept).filter_by(concept_id=concept.id).order_by(SourceConcept.id).first()
    source_id = link.source_id if link else None
    source_chunk_id = link.source_chunk_id if link else None
    lineage = [
        {
            "source_id": source_id,
            "source_chunk_id": source_chunk_id,
            "concept_id": concept.id,
            "evidence_text": link.evidence_text if link else concept.description,
            "lineage_reason": "concept",
        }
    ]
    draft = create_question_draft(
        db,
        course_code=course_code,
        created_by=user_id,
        source_id=source_id,
        source_chunk_id=source_chunk_id,
        concept_id=concept.id,
        stem=f"Which statement best describes {concept.name}?",
        choices=placeholder_choices(concept.name),
        correct_answer=[],
        explanation="",
        generation_method="rule_based",
        lineage=lineage,
    )
    return [draft]


def published_status_for_draft(draft: QuestionDraft) -> str:
    return "reviewed" if draft.status == "reviewed" else "verified"


def published_confidence_for_status(status_value: str) -> int:
    return 7 if status_value == "reviewed" else 9


def explanation_text_for_publish(draft: QuestionDraft) -> str:
    if str(draft.explanation or "").strip():
        return draft.explanation
    data = draft.explanation_json if isinstance(draft.explanation_json, dict) else {}
    parts = []
    correct = str(data.get("correct") or "").strip()
    if correct:
        parts.append(correct)
    incorrect = data.get("incorrect") if isinstance(data.get("incorrect"), dict) else {}
    for choice, reason in incorrect.items():
        reason_text = str(reason or "").strip()
        if reason_text:
            parts.append(f"{choice}: {reason_text}")
    return "\n".join(parts)


def why_wrong_for_publish(draft: QuestionDraft) -> dict[str, str]:
    data = draft.explanation_json if isinstance(draft.explanation_json, dict) else {}
    incorrect = data.get("incorrect") if isinstance(data.get("incorrect"), dict) else {}
    return {str(choice): str(reason) for choice, reason in incorrect.items() if str(reason).strip()}


def publish_draft(db: Session, draft: QuestionDraft, published_by: int | None = None, notes: str = "") -> QuestionDraft:
    course = get_course_or_404(db, draft.course_code)
    question = db.get(Question, draft.published_question_id) if draft.published_question_id else None
    previous_status = question.status if question else None
    action = "republished" if question else "published"
    if not question:
        question = Question(
            course_id=course.id,
            legacy_id=f"{course.course_code}-draft-{draft.id}",
            question_text=draft.stem,
            answer_json=draft.correct_answer_json,
        )
    question.course_id = course.id
    question.concept_id = draft.concept_id
    question.question_type = draft.question_type
    question.topic = draft.concept.name if draft.concept else ""
    question.subtopic = ""
    question.difficulty = draft.difficulty
    question.oa_probability = draft.oa_probability
    question.question_text = draft.stem
    question.choices_json = draft.choices_json
    question.answer_json = draft.correct_answer_json
    question.explanation = explanation_text_for_publish(draft)
    question.why_wrong_json = why_wrong_for_publish(draft)
    question.memory = ""
    question.exam_tip = ""
    question.status = published_status_for_draft(draft)
    question.confidence = published_confidence_for_status(question.status)
    question.lineage_json = {
        "draftId": draft.id,
        "sourceMaterialId": draft.source_id,
        "sourceChunkId": draft.source_chunk_id,
        "conceptId": draft.concept_id,
        "generationMethod": draft.generation_method,
        "explanationJson": draft.explanation_json or {},
        "sourceType": draft.source.source_type if draft.source else "",
        "sourceTags": [draft.source.title] if draft.source else [],
        "draftLineage": [
            {
                "sourceMaterialId": row.source_id,
                "sourceChunkId": row.source_chunk_id,
                "conceptId": row.concept_id,
                "evidence": row.evidence_text,
                "reason": row.lineage_reason,
            }
            for row in draft.lineage
        ],
    }
    db.add(question)
    db.flush()
    replace_published_lineage_snapshot(db, question, draft)
    record_publish_history(
        db,
        question=question,
        action=action,
        previous_status=previous_status,
        new_status=question.status,
        published_by=published_by,
        draft_id=draft.id,
        course_code=course.course_code,
        notes=notes,
    )
    draft.published_question_id = question.id
    draft.status = "published"
    draft.confidence = "verified"
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft
