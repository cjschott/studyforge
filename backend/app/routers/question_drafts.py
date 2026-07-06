from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Concept, QuestionDraft, QuestionDraftLineage, SourceMaterial, User
from app.schemas import (
    QuestionDraftCreate,
    QuestionDraftGenerationOut,
    QuestionDraftGenerationRequest,
    QuestionDraftOut,
    QuestionDraftPatch,
    QuestionDraftWarningOut,
)
from app.services.question_drafting_service import (
    create_question_draft,
    draft_questions_for_concept,
    draft_questions_for_source,
    draft_status,
    normalize_course_code,
    publish_draft,
)
from app.services.question_validation_service import (
    high_severity_warnings,
    refresh_question_draft_warnings,
    stored_warnings_for_draft,
)
from app.services.question_publish_service import publish_history_to_dict


router = APIRouter(tags=["question-drafts"])


def iso(value):
    if not value:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def get_draft_or_404(db: Session, draft_id: int) -> QuestionDraft:
    draft = db.get(QuestionDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question draft not found")
    return draft


def get_material_or_404(db: Session, material_id: int) -> SourceMaterial:
    material = db.get(SourceMaterial, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source material not found")
    return material


def get_concept_or_404(db: Session, concept_id: int) -> Concept:
    concept = db.get(Concept, concept_id)
    if not concept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found")
    return concept


def lineage_out(row: QuestionDraftLineage) -> dict:
    return {
        "id": row.id,
        "draft_id": row.draft_id,
        "source_id": row.source_id,
        "source_title": row.source.title if row.source else None,
        "source_type": row.source.source_type if row.source else None,
        "source_authority_level": row.source.authority_level if row.source else None,
        "source_confidence": row.source.confidence if row.source else None,
        "source_verification_status": row.source.verification_status if row.source else None,
        "source_chunk_id": row.source_chunk_id,
        "source_chunk_number": row.chunk.chunk_number if row.chunk else None,
        "source_page_number": row.chunk.page_number if row.chunk else None,
        "concept_id": row.concept_id,
        "concept_name": row.concept.name if row.concept else None,
        "concept_status": row.concept.status if row.concept else None,
        "evidence_text": row.evidence_text,
        "lineage_reason": row.lineage_reason,
        "created_at": iso(row.created_at),
    }


def draft_out(db: Session, draft: QuestionDraft) -> dict:
    return {
        "id": draft.id,
        "course_code": draft.course_code,
        "source_id": draft.source_id,
        "source_title": draft.source.title if draft.source else None,
        "source_type": draft.source.source_type if draft.source else None,
        "source_authority_level": draft.source.authority_level if draft.source else None,
        "source_confidence": draft.source.confidence if draft.source else None,
        "source_verification_status": draft.source.verification_status if draft.source else None,
        "source_chunk_id": draft.source_chunk_id,
        "source_chunk_number": draft.chunk.chunk_number if draft.chunk else None,
        "concept_id": draft.concept_id,
        "concept_name": draft.concept.name if draft.concept else None,
        "concept_status": draft.concept.status if draft.concept else None,
        "published_question_id": draft.published_question_id,
        "question_type": draft.question_type,
        "stem": draft.stem,
        "choices": draft.choices_json,
        "correct_answer": draft.correct_answer_json,
        "explanation": draft.explanation,
        "explanation_json": draft.explanation_json or {},
        "difficulty": draft.difficulty,
        "oa_probability": draft.oa_probability,
        "status": draft.status,
        "confidence": draft.confidence,
        "generation_method": draft.generation_method,
        "created_by": draft.created_by,
        "created_at": iso(draft.created_at),
        "updated_at": iso(draft.updated_at),
        "lineage": [lineage_out(row) for row in draft.lineage],
        "warnings": stored_warnings_for_draft(draft),
        "publish_history": [
            publish_history_to_dict(row)
            for row in sorted(draft.published_question.publish_history, key=lambda item: item.id)
        ]
        if draft.published_question
        else [],
        "published_question_status": draft.published_question.status if draft.published_question else None,
    }


def blocking_warning_response(action: str, warnings: list[dict]) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": f"Cannot {action} question draft while high-severity validation warnings exist.",
            "warnings": warnings,
        },
    )


@router.get("/api/question-drafts", response_model=list[QuestionDraftOut])
def list_question_drafts(
    status_filter: str | None = Query(default=None, alias="status"),
    course_code: str | None = Query(default=None),
    source_id: int | None = Query(default=None),
    concept_id: int | None = Query(default=None),
    warnings_only: bool = Query(default=False),
    search: str | None = Query(default=None),
    include_rejected: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(QuestionDraft)
    if not include_rejected:
        query = query.filter(QuestionDraft.status != "rejected")
    if status_filter:
        query = query.filter(QuestionDraft.status == status_filter)
    if course_code:
        query = query.filter(QuestionDraft.course_code == course_code)
    if source_id is not None:
        query = query.filter(QuestionDraft.source_id == source_id)
    if concept_id is not None:
        query = query.filter(QuestionDraft.concept_id == concept_id)
    if search:
        like = f"%{search.strip().lower()}%"
        query = query.filter(or_(QuestionDraft.stem.ilike(like), QuestionDraft.explanation.ilike(like)))
    drafts = query.order_by(QuestionDraft.updated_at.desc(), QuestionDraft.id.desc()).limit(500).all()
    if warnings_only:
        drafts = [draft for draft in drafts if draft.warnings]
    return [draft_out(db, draft) for draft in drafts]


@router.post("/api/question-drafts", response_model=QuestionDraftOut, status_code=status.HTTP_201_CREATED)
def create_draft(
    payload: QuestionDraftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    draft = create_question_draft(
        db,
        course_code=payload.course_code,
        created_by=current_user.id,
        source_id=payload.source_id,
        source_chunk_id=payload.source_chunk_id,
        concept_id=payload.concept_id,
        question_type=payload.question_type,
        stem=payload.stem,
        choices=payload.choices,
        correct_answer=payload.correct_answer,
        explanation=payload.explanation,
        explanation_json=payload.explanation_json,
        difficulty=payload.difficulty,
        oa_probability=payload.oa_probability,
        status_value=payload.status,
        confidence=payload.confidence,
        generation_method=payload.generation_method,
        lineage=[item.model_dump() for item in payload.lineage] if payload.lineage else None,
    )
    return draft_out(db, draft)


@router.get("/api/question-drafts/{draft_id}", response_model=QuestionDraftOut)
def get_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return draft_out(db, get_draft_or_404(db, draft_id))


@router.put("/api/question-drafts/{draft_id}", response_model=QuestionDraftOut)
def update_draft(
    draft_id: int,
    payload: QuestionDraftPatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    draft = get_draft_or_404(db, draft_id)
    field_map = {
        "course_code": "course_code",
        "source_id": "source_id",
        "source_chunk_id": "source_chunk_id",
        "concept_id": "concept_id",
        "question_type": "question_type",
        "stem": "stem",
        "choices": "choices_json",
        "correct_answer": "correct_answer_json",
        "explanation": "explanation",
        "explanation_json": "explanation_json",
        "difficulty": "difficulty",
        "oa_probability": "oa_probability",
        "status": "status",
        "confidence": "confidence",
        "generation_method": "generation_method",
    }
    patch = payload.model_dump(exclude_unset=True)
    lineage = patch.pop("lineage", None)
    for key, value in patch.items():
        if key == "explanation_json" and value is None:
            value = {}
        setattr(draft, field_map[key], value)
    if lineage is not None:
        draft.lineage.clear()
        db.flush()
        for item in lineage:
            draft.lineage.append(QuestionDraftLineage(**item))
    db.add(draft)
    db.flush()
    refresh_question_draft_warnings(db, draft)
    db.commit()
    db.refresh(draft)
    return draft_out(db, draft)


def update_draft_status(
    db: Session,
    draft_id: int,
    next_status: str,
    next_confidence: str | None = None,
    *,
    block_high_warnings: bool = False,
) -> dict | JSONResponse:
    draft = get_draft_or_404(db, draft_id)
    warnings = refresh_question_draft_warnings(db, draft)
    blocking = high_severity_warnings(warnings)
    if block_high_warnings and blocking:
        db.commit()
        return blocking_warning_response(next_status, blocking)
    draft_status(draft, next_status, next_confidence)
    db.add(draft)
    db.flush()
    refresh_question_draft_warnings(db, draft)
    db.commit()
    db.refresh(draft)
    return draft_out(db, draft)


@router.get("/api/question-drafts/{draft_id}/warnings", response_model=list[QuestionDraftWarningOut])
def get_draft_warnings(
    draft_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    draft = get_draft_or_404(db, draft_id)
    return stored_warnings_for_draft(draft)


@router.post("/api/question-drafts/{draft_id}/validate", response_model=QuestionDraftOut)
def validate_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    draft = get_draft_or_404(db, draft_id)
    refresh_question_draft_warnings(db, draft)
    db.commit()
    db.refresh(draft)
    return draft_out(db, draft)


@router.post("/api/question-drafts/{draft_id}/review", response_model=QuestionDraftOut)
def review_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    return update_draft_status(db, draft_id, "reviewed", "reviewed")


@router.post("/api/question-drafts/{draft_id}/verify", response_model=QuestionDraftOut)
def verify_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    return update_draft_status(db, draft_id, "verified", "verified", block_high_warnings=True)


@router.post("/api/question-drafts/{draft_id}/reject", response_model=QuestionDraftOut)
def reject_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    return update_draft_status(db, draft_id, "rejected", "unverified")


@router.post("/api/question-drafts/{draft_id}/publish", response_model=QuestionDraftOut)
def publish_question_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "instructor")),
):
    draft = get_draft_or_404(db, draft_id)
    warnings = refresh_question_draft_warnings(db, draft)
    blocking = high_severity_warnings(warnings)
    if blocking:
        db.commit()
        return blocking_warning_response("publish", blocking)
    draft = publish_draft(db, draft, published_by=current_user.id)
    return draft_out(db, draft)


@router.post("/api/source-materials/{material_id}/draft-questions", response_model=QuestionDraftGenerationOut)
def draft_questions_from_source(
    material_id: int,
    payload: QuestionDraftGenerationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    material = get_material_or_404(db, material_id)
    payload = payload or QuestionDraftGenerationRequest()
    course_code = normalize_course_code(db, payload.course_code)
    drafts = draft_questions_for_source(db, material, course_code, current_user.id, payload.limit)
    return {
        "target_type": "source_material",
        "target_id": material.id,
        "drafts_created": len(drafts),
        "drafts": [draft_out(db, draft) for draft in drafts],
    }


@router.post("/api/concepts/{concept_id}/draft-questions", response_model=QuestionDraftGenerationOut)
def draft_questions_from_concept(
    concept_id: int,
    payload: QuestionDraftGenerationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    concept = get_concept_or_404(db, concept_id)
    payload = payload or QuestionDraftGenerationRequest()
    course_code = normalize_course_code(db, payload.course_code, concept)
    drafts = draft_questions_for_concept(db, concept, course_code, current_user.id)
    return {
        "target_type": "concept",
        "target_id": concept.id,
        "drafts_created": len(drafts),
        "drafts": [draft_out(db, draft) for draft in drafts],
    }


@router.post("/api/course-builder/draft-questions", response_model=QuestionDraftGenerationOut)
def draft_questions_from_course_builder(
    payload: QuestionDraftGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course_code = normalize_course_code(db, payload.course_code)
    drafts: list[QuestionDraft] = []
    remaining = payload.limit
    for material_id in payload.source_material_ids:
        if remaining <= 0:
            break
        material = get_material_or_404(db, material_id)
        created = draft_questions_for_source(db, material, course_code, current_user.id, remaining)
        drafts.extend(created)
        remaining = payload.limit - len(drafts)
    for concept_id in payload.concept_ids:
        if remaining <= 0:
            break
        concept = get_concept_or_404(db, concept_id)
        drafts.extend(draft_questions_for_concept(db, concept, normalize_course_code(db, course_code, concept), current_user.id))
        remaining = payload.limit - len(drafts)
    return {
        "target_type": "course_builder",
        "target_id": None,
        "drafts_created": len(drafts),
        "drafts": [draft_out(db, draft) for draft in drafts],
    }
