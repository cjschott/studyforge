from typing import Any

from sqlalchemy.orm import Session

from app.models import PublishedQuestionLineage, Question, QuestionDraft, QuestionPublishHistory


def iso(value):
    if not value:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def publish_history_to_dict(row: QuestionPublishHistory) -> dict[str, Any]:
    return {
        "id": row.id,
        "draft_id": row.draft_id,
        "question_id": row.question_id,
        "course_code": row.course_code,
        "action": row.action,
        "previous_status": row.previous_status,
        "new_status": row.new_status,
        "published_by": row.published_by,
        "notes": row.notes,
        "created_at": iso(row.created_at),
    }


def published_lineage_to_dict(row: PublishedQuestionLineage) -> dict[str, Any]:
    return {
        "id": row.id,
        "question_id": row.question_id,
        "source_id": row.source_id,
        "source_chunk_id": row.source_chunk_id,
        "concept_id": row.concept_id,
        "evidence_text": row.evidence_text,
        "lineage_reason": row.lineage_reason,
        "source_title": row.source_title,
        "source_type": row.source_type,
        "source_confidence": row.source_confidence,
        "source_verification_status": row.source_verification_status,
        "created_at": iso(row.created_at),
    }


def record_publish_history(
    db: Session,
    *,
    question: Question,
    action: str,
    previous_status: str | None,
    new_status: str,
    published_by: int | None,
    draft_id: int | None = None,
    course_code: str | None = None,
    notes: str = "",
) -> QuestionPublishHistory:
    row = QuestionPublishHistory(
        draft_id=draft_id,
        question_id=question.id,
        course_code=course_code or question.course.course_code,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        published_by=published_by,
        notes=notes or "",
    )
    db.add(row)
    db.flush()
    return row


def replace_published_lineage_snapshot(db: Session, question: Question, draft: QuestionDraft) -> list[PublishedQuestionLineage]:
    db.query(PublishedQuestionLineage).filter(PublishedQuestionLineage.question_id == question.id).delete(
        synchronize_session=False
    )
    db.flush()
    rows: list[PublishedQuestionLineage] = []
    for item in draft.lineage:
        source = item.source
        row = PublishedQuestionLineage(
            question_id=question.id,
            source_id=item.source_id,
            source_chunk_id=item.source_chunk_id,
            concept_id=item.concept_id,
            evidence_text=item.evidence_text or "",
            lineage_reason=item.lineage_reason or "",
            source_title=source.title if source else "",
            source_type=source.source_type if source else "",
            source_confidence=source.confidence if source else "",
            source_verification_status=source.verification_status if source else "",
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows
