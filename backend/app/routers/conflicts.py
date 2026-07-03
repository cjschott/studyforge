from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Concept, SourceConflict, SourceMaterial, User
from app.schemas import ConflictDetectionOut, SourceConflictOut, SourceConflictPatch
from app.services.conflict_detection_service import detect_conflicts_for_concept, detect_conflicts_for_source


router = APIRouter(tags=["conflicts"])

CONFLICT_TYPES = {
    "conflicting_definition",
    "conflicting_answer",
    "outdated_reference",
    "unsupported_claim",
    "duplicate_concept",
    "low_authority_source",
    "missing_lineage",
    "unclear_explanation",
    "possible_bad_answer",
}
SEVERITIES = {"low", "medium", "high"}
STATUSES = {"generated", "needs_review", "reviewed", "resolved", "rejected"}
REVIEWER_ROLES = {"admin", "instructor"}


def iso(value):
    if not value:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def ensure_reviewer(user: User):
    if user.role not in REVIEWER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


def get_conflict_or_404(db: Session, conflict_id: int) -> SourceConflict:
    conflict = db.get(SourceConflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflict not found")
    return conflict


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


def conflict_out(conflict: SourceConflict) -> dict:
    return {
        "id": conflict.id,
        "concept_id": conflict.concept_id,
        "concept_name": conflict.concept.name if conflict.concept else None,
        "source_id_a": conflict.source_id_a,
        "source_title_a": conflict.source_a.title if conflict.source_a else None,
        "source_type_a": conflict.source_a.source_type if conflict.source_a else None,
        "source_authority_level_a": conflict.source_a.authority_level if conflict.source_a else None,
        "source_confidence_a": conflict.source_a.confidence if conflict.source_a else None,
        "source_verification_status_a": conflict.source_a.verification_status if conflict.source_a else None,
        "source_chunk_id_a": conflict.source_chunk_id_a,
        "source_chunk_number_a": conflict.chunk_a.chunk_number if conflict.chunk_a else None,
        "source_page_number_a": conflict.chunk_a.page_number if conflict.chunk_a else None,
        "source_id_b": conflict.source_id_b,
        "source_title_b": conflict.source_b.title if conflict.source_b else None,
        "source_type_b": conflict.source_b.source_type if conflict.source_b else None,
        "source_authority_level_b": conflict.source_b.authority_level if conflict.source_b else None,
        "source_confidence_b": conflict.source_b.confidence if conflict.source_b else None,
        "source_verification_status_b": conflict.source_b.verification_status if conflict.source_b else None,
        "source_chunk_id_b": conflict.source_chunk_id_b,
        "source_chunk_number_b": conflict.chunk_b.chunk_number if conflict.chunk_b else None,
        "source_page_number_b": conflict.chunk_b.page_number if conflict.chunk_b else None,
        "conflict_type": conflict.conflict_type,
        "summary": conflict.summary,
        "evidence_a": conflict.evidence_a,
        "evidence_b": conflict.evidence_b,
        "severity": conflict.severity,
        "status": conflict.status,
        "detection_method": conflict.detection_method,
        "created_at": iso(conflict.created_at),
        "updated_at": iso(conflict.updated_at),
    }


@router.get("/api/conflicts", response_model=list[SourceConflictOut])
def list_conflicts(
    severity: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    conflict_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    source_id: int | None = Query(default=None),
    concept_id: int | None = Query(default=None),
    include_resolved: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(SourceConflict)
    if not include_resolved:
        query = query.filter(SourceConflict.status != "resolved")
    if severity:
        if severity not in SEVERITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid severity")
        query = query.filter(SourceConflict.severity == severity)
    if status_filter:
        if status_filter not in STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        query = query.filter(SourceConflict.status == status_filter)
    if conflict_type:
        if conflict_type not in CONFLICT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conflict_type")
        query = query.filter(SourceConflict.conflict_type == conflict_type)
    if source_id is not None:
        query = query.filter(or_(SourceConflict.source_id_a == source_id, SourceConflict.source_id_b == source_id))
    if concept_id is not None:
        query = query.filter(SourceConflict.concept_id == concept_id)
    if search:
        like = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                SourceConflict.summary.ilike(like),
                SourceConflict.evidence_a.ilike(like),
                SourceConflict.evidence_b.ilike(like),
            )
        )
    conflicts = query.order_by(SourceConflict.created_at.desc(), SourceConflict.id.desc()).all()
    return [conflict_out(conflict) for conflict in conflicts]


@router.get("/api/conflicts/{conflict_id}", response_model=SourceConflictOut)
def get_conflict(
    conflict_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return conflict_out(get_conflict_or_404(db, conflict_id))


@router.put("/api/conflicts/{conflict_id}", response_model=SourceConflictOut)
def update_conflict(
    conflict_id: int,
    payload: SourceConflictPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conflict = get_conflict_or_404(db, conflict_id)
    patch = payload.model_dump(exclude_unset=True)
    if patch.get("status") in {"resolved", "rejected"}:
        ensure_reviewer(current_user)
    for key, value in patch.items():
        if value is not None:
            setattr(conflict, key, value)
    db.add(conflict)
    db.commit()
    db.refresh(conflict)
    return conflict_out(conflict)


@router.post("/api/conflicts/{conflict_id}/resolve", response_model=SourceConflictOut)
def resolve_conflict(
    conflict_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_reviewer(current_user)
    conflict = get_conflict_or_404(db, conflict_id)
    conflict.status = "resolved"
    db.add(conflict)
    db.commit()
    db.refresh(conflict)
    return conflict_out(conflict)


@router.post("/api/source-materials/{material_id}/detect-conflicts", response_model=ConflictDetectionOut)
def detect_source_conflicts(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    material = get_material_or_404(db, material_id)
    result = detect_conflicts_for_source(db, material)
    return {
        "target_type": "source_material",
        "target_id": material.id,
        "conflicts_created": result.conflicts_created,
        "conflicts": [conflict_out(conflict) for conflict in result.conflicts],
    }


@router.post("/api/concepts/{concept_id}/detect-conflicts", response_model=ConflictDetectionOut)
def detect_concept_conflicts(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    concept = get_concept_or_404(db, concept_id)
    result = detect_conflicts_for_concept(db, concept)
    return {
        "target_type": "concept",
        "target_id": concept.id,
        "conflicts_created": result.conflicts_created,
        "conflicts": [conflict_out(conflict) for conflict in result.conflicts],
    }
