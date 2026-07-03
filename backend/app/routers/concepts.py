from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Concept, ConceptAlias, ConceptRelationship, Course, SourceChunk, SourceConcept, SourceMaterial, User
from app.schemas import (
    ConceptAliasCreate,
    ConceptAliasOut,
    ConceptCreate,
    ConceptEvidenceOut,
    ConceptExtractionOut,
    ConceptMergeOut,
    ConceptMergeRequest,
    ConceptOut,
    ConceptPatch,
    ConceptRelationshipCreate,
    ConceptRelationshipOut,
    ConceptRelationshipPatch,
    ConceptSourceOut,
    SourceConceptLinkOut,
)
from app.services.concept_extraction_service import (
    extract_concepts_for_source,
    normalize_concept_name,
    normalized_confidence,
)


router = APIRouter(tags=["concepts"])

CONCEPT_STATUSES = {"generated", "reviewed", "verified", "rejected"}
CONCEPT_CONFIDENCES = {"generated", "reviewed", "verified", "unverified"}


def iso(value):
    if not value:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def normalized_status(value) -> str:
    return value if value in CONCEPT_STATUSES else "generated"


def concept_alias_values(concept: Concept) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for alias in concept.aliases:
        normalized = normalize_concept_name(alias.alias)
        if normalized and normalized not in seen:
            values.append(alias.alias)
            seen.add(normalized)
    legacy_aliases = concept.aliases_json if isinstance(concept.aliases_json, list) else []
    for alias in legacy_aliases:
        normalized = normalize_concept_name(str(alias))
        if normalized and normalized not in seen:
            values.append(str(alias))
            seen.add(normalized)
    return values


def concept_source_count(concept: Concept, db: Session) -> int:
    return (
        db.query(func.count(func.distinct(SourceConcept.source_id)))
        .filter(SourceConcept.concept_id == concept.id)
        .scalar()
        or 0
    )


def concept_relationship_count(concept: Concept, db: Session) -> int:
    return (
        db.query(func.count(ConceptRelationship.id))
        .filter(
            or_(
                ConceptRelationship.concept_a_id == concept.id,
                ConceptRelationship.concept_b_id == concept.id,
            )
        )
        .scalar()
        or 0
    )


def concept_out(concept: Concept, db: Session) -> dict:
    normalized_name = concept.normalized_name or normalize_concept_name(concept.name)
    return {
        "id": concept.id,
        "name": concept.name,
        "normalized_name": normalized_name,
        "description": concept.description or "",
        "course_code": concept.course_code,
        "status": normalized_status(concept.status),
        "confidence": normalized_confidence(concept.confidence),
        "aliases": concept_alias_values(concept),
        "source_count": concept_source_count(concept, db),
        "relationship_count": concept_relationship_count(concept, db),
        "created_at": iso(concept.created_at),
        "updated_at": iso(concept.updated_at),
    }


def source_concept_link_out(link: SourceConcept, db: Session) -> dict:
    return {
        "id": link.id,
        "source_id": link.source_id,
        "source_chunk_id": link.source_chunk_id,
        "evidence_text": link.evidence_text,
        "confidence_score": link.confidence_score,
        "extraction_method": link.extraction_method,
        "created_at": iso(link.created_at),
        "concept": concept_out(link.concept, db),
    }


def concept_source_out(link: SourceConcept) -> dict:
    return {
        "id": link.id,
        "source_id": link.source_id,
        "source_title": link.source.title if link.source else "",
        "source_chunk_id": link.source_chunk_id,
        "chunk_number": link.chunk.chunk_number if link.chunk else 0,
        "page_number": link.chunk.page_number if link.chunk else None,
        "heading": link.chunk.heading if link.chunk else "",
        "evidence_text": link.evidence_text,
        "confidence_score": link.confidence_score,
        "extraction_method": link.extraction_method,
        "created_at": iso(link.created_at),
    }


def concept_evidence_out(link: SourceConcept) -> dict:
    return {
        "id": link.id,
        "source_id": link.source_id,
        "source_title": link.source.title if link.source else "",
        "source_type": link.source.source_type if link.source else "",
        "source_confidence": link.source.confidence if link.source else "",
        "verification_status": link.source.verification_status if link.source else "",
        "source_chunk_id": link.source_chunk_id,
        "chunk_number": link.chunk.chunk_number if link.chunk else 0,
        "page_number": link.chunk.page_number if link.chunk else None,
        "heading": link.chunk.heading if link.chunk else "",
        "evidence_text": link.evidence_text,
        "confidence_score": link.confidence_score,
        "extraction_method": link.extraction_method,
        "created_at": iso(link.created_at),
    }


def relationship_out(relationship: ConceptRelationship) -> dict:
    return {
        "id": relationship.id,
        "concept_a_id": relationship.concept_a_id,
        "concept_a_name": relationship.concept_a.name if relationship.concept_a else "",
        "concept_b_id": relationship.concept_b_id,
        "concept_b_name": relationship.concept_b.name if relationship.concept_b else "",
        "relationship_type": relationship.relationship_type,
        "confidence_score": relationship.confidence_score,
        "status": normalized_status(relationship.status),
        "created_at": iso(relationship.created_at),
    }


def get_concept_or_404(db: Session, concept_id: int) -> Concept:
    concept = db.get(Concept, concept_id)
    if not concept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found")
    return concept


def get_relationship_or_404(db: Session, relationship_id: int) -> ConceptRelationship:
    relationship = db.get(ConceptRelationship, relationship_id)
    if not relationship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept relationship not found")
    return relationship


def get_material_or_404(db: Session, material_id: int) -> SourceMaterial:
    material = db.get(SourceMaterial, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source material not found")
    return material


def alias_out(alias: ConceptAlias) -> dict:
    return {
        "id": alias.id,
        "concept_id": alias.concept_id,
        "alias": alias.alias,
        "normalized_alias": alias.normalized_alias,
    }


def sync_aliases_json(concept: Concept):
    concept.aliases_json = [alias.alias for alias in concept.aliases]


def alias_exists(concept: Concept, normalized_alias: str) -> bool:
    if not normalized_alias:
        return False
    if normalized_alias == (concept.normalized_name or normalize_concept_name(concept.name)):
        return True
    return any(alias.normalized_alias == normalized_alias for alias in concept.aliases)


def add_alias_to_concept(db: Session, concept: Concept, alias_value: str) -> ConceptAlias | None:
    alias_value = alias_value.strip()
    normalized_alias = normalize_concept_name(alias_value)
    if not alias_value or alias_exists(concept, normalized_alias):
        return None
    alias = ConceptAlias(alias=alias_value, normalized_alias=normalized_alias)
    concept.aliases.append(alias)
    sync_aliases_json(concept)
    db.add(concept)
    db.flush()
    return alias


def find_concept_by_normalized(db: Session, normalized_name: str) -> Concept | None:
    return (
        db.query(Concept)
        .filter(or_(Concept.normalized_name == normalized_name, func.lower(Concept.name) == normalized_name))
        .order_by(Concept.id)
        .first()
    )


def apply_course_link(db: Session, concept: Concept, course_code: str | None):
    concept.course_code = course_code
    if not course_code:
        concept.course_id = None
        return
    course = db.query(Course).filter_by(course_code=course_code).one_or_none()
    concept.course_id = course.id if course else None


def replace_aliases(db: Session, concept: Concept, aliases: list[str]):
    concept.aliases.clear()
    concept.aliases_json = []
    seen = {concept.normalized_name or normalize_concept_name(concept.name)}
    for alias in aliases:
        alias = alias.strip()
        normalized = normalize_concept_name(alias)
        if not alias or not normalized or normalized in seen:
            continue
        concept.aliases.append(ConceptAlias(alias=alias, normalized_alias=normalized))
        concept.aliases_json.append(alias)
        seen.add(normalized)
    db.add(concept)


def set_concept_review_state(db: Session, concept: Concept, next_status: str, next_confidence: str) -> Concept:
    concept.status = next_status
    concept.confidence = next_confidence
    db.add(concept)
    db.commit()
    db.refresh(concept)
    return concept


@router.get("/api/concepts", response_model=list[ConceptOut])
def list_concepts(
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    course_code: str | None = Query(default=None),
    include_rejected: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Concept)
    if not include_rejected:
        query = query.filter(Concept.status != "rejected")
    if status_filter:
        if status_filter not in CONCEPT_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        query = query.filter(Concept.status == status_filter)
    if course_code:
        query = query.filter(Concept.course_code == course_code)
    if search:
        normalized = normalize_concept_name(search)
        like = f"%{normalized}%"
        query = query.filter(or_(Concept.normalized_name.like(like), func.lower(Concept.name).like(like)))
    return [concept_out(concept, db) for concept in query.order_by(Concept.name).all()]


@router.post("/api/concepts", response_model=ConceptOut, status_code=status.HTTP_201_CREATED)
def create_concept(
    payload: ConceptCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    name = payload.name.strip()
    normalized = normalize_concept_name(name)
    if find_concept_by_normalized(db, normalized):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concept already exists")
    concept = Concept(
        name=name,
        normalized_name=normalized,
        description=payload.description,
        status=payload.status,
        confidence=payload.confidence,
    )
    apply_course_link(db, concept, payload.course_code)
    db.add(concept)
    db.flush()
    replace_aliases(db, concept, payload.aliases)
    db.commit()
    db.refresh(concept)
    return concept_out(concept, db)


@router.get("/api/concepts/{concept_id}", response_model=ConceptOut)
def get_concept(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return concept_out(get_concept_or_404(db, concept_id), db)


@router.put("/api/concepts/{concept_id}", response_model=ConceptOut)
def update_concept(
    concept_id: int,
    payload: ConceptPatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    concept = get_concept_or_404(db, concept_id)
    patch = payload.model_dump(exclude_unset=True)
    if "name" in patch and patch["name"] is not None:
        name = patch["name"].strip()
        normalized = normalize_concept_name(name)
        existing = find_concept_by_normalized(db, normalized)
        if existing and existing.id != concept.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concept already exists")
        concept.name = name
        concept.normalized_name = normalized
    for key in ["description", "status", "confidence"]:
        if key in patch and patch[key] is not None:
            setattr(concept, key, patch[key])
    if "course_code" in patch:
        apply_course_link(db, concept, patch["course_code"])
    if "aliases" in patch and patch["aliases"] is not None:
        replace_aliases(db, concept, patch["aliases"])
    db.add(concept)
    db.commit()
    db.refresh(concept)
    return concept_out(concept, db)


@router.delete("/api/concepts/{concept_id}")
def delete_concept(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    concept = get_concept_or_404(db, concept_id)
    concept.status = "rejected"
    db.add(concept)
    db.commit()
    return {"ok": True, "status": "rejected"}


@router.post("/api/concepts/{concept_id}/review", response_model=ConceptOut)
def review_concept(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return concept_out(set_concept_review_state(db, get_concept_or_404(db, concept_id), "reviewed", "reviewed"), db)


@router.post("/api/concepts/{concept_id}/verify", response_model=ConceptOut)
def verify_concept(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return concept_out(set_concept_review_state(db, get_concept_or_404(db, concept_id), "verified", "verified"), db)


@router.post("/api/concepts/{concept_id}/reject", response_model=ConceptOut)
def reject_concept(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return concept_out(set_concept_review_state(db, get_concept_or_404(db, concept_id), "rejected", "unverified"), db)


@router.post("/api/concepts/{concept_id}/restore", response_model=ConceptOut)
def restore_concept(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return concept_out(set_concept_review_state(db, get_concept_or_404(db, concept_id), "generated", "unverified"), db)


@router.get("/api/concepts/{concept_id}/aliases", response_model=list[ConceptAliasOut])
def list_concept_aliases(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    concept = get_concept_or_404(db, concept_id)
    return [alias_out(alias) for alias in sorted(concept.aliases, key=lambda item: item.alias.lower())]


@router.post("/api/concepts/{concept_id}/aliases", response_model=ConceptAliasOut, status_code=status.HTTP_201_CREATED)
def create_concept_alias(
    concept_id: int,
    payload: ConceptAliasCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    concept = get_concept_or_404(db, concept_id)
    normalized_alias = normalize_concept_name(payload.alias)
    if alias_exists(concept, normalized_alias):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate concept alias")
    alias = add_alias_to_concept(db, concept, payload.alias)
    if not alias:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate concept alias")
    sync_aliases_json(concept)
    db.add(concept)
    db.commit()
    db.refresh(alias)
    return alias_out(alias)


@router.delete("/api/concepts/{concept_id}/aliases/{alias_id}")
def delete_concept_alias(
    concept_id: int,
    alias_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    concept = get_concept_or_404(db, concept_id)
    alias = db.get(ConceptAlias, alias_id)
    if not alias or alias.concept_id != concept.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept alias not found")
    db.delete(alias)
    db.flush()
    db.refresh(concept)
    sync_aliases_json(concept)
    db.add(concept)
    db.commit()
    return {"ok": True}


@router.post("/api/concepts/{concept_id}/merge", response_model=ConceptMergeOut)
def merge_concept(
    concept_id: int,
    payload: ConceptMergeRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    source = get_concept_or_404(db, concept_id)
    target = get_concept_or_404(db, payload.target_concept_id)
    if source.id == target.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot merge a concept into itself")

    aliases_moved = 0
    if add_alias_to_concept(db, target, source.name):
        aliases_moved += 1
    for alias_value in concept_alias_values(source):
        if add_alias_to_concept(db, target, alias_value):
            aliases_moved += 1
    source.aliases.clear()
    source.aliases_json = []

    source_links_moved = 0
    for link in list(source.source_links):
        duplicate = (
            db.query(SourceConcept)
            .filter_by(source_chunk_id=link.source_chunk_id, concept_id=target.id)
            .one_or_none()
        )
        if duplicate:
            if link.evidence_text and link.evidence_text not in duplicate.evidence_text:
                duplicate.evidence_text = f"{duplicate.evidence_text}\n{link.evidence_text}".strip()[:1200]
            db.delete(link)
        else:
            link.concept_id = target.id
            db.add(link)
        source_links_moved += 1

    relationships_moved = 0
    relationships = (
        db.query(ConceptRelationship)
        .filter(or_(ConceptRelationship.concept_a_id == source.id, ConceptRelationship.concept_b_id == source.id))
        .all()
    )
    for relationship in relationships:
        if {relationship.concept_a_id, relationship.concept_b_id} == {source.id, target.id}:
            relationship.status = "rejected"
            db.add(relationship)
            continue
        if relationship.concept_a_id == source.id:
            relationship.concept_a_id = target.id
            relationships_moved += 1
        if relationship.concept_b_id == source.id:
            relationship.concept_b_id = target.id
            relationships_moved += 1
        if relationship.concept_a_id == relationship.concept_b_id:
            relationship.status = "rejected"
        db.add(relationship)

    source.status = "rejected"
    source.confidence = "unverified"
    db.add_all([source, target])
    db.commit()
    db.refresh(source)
    db.refresh(target)
    return {
        "source_concept": concept_out(source, db),
        "target_concept": concept_out(target, db),
        "aliases_moved": aliases_moved,
        "source_links_moved": source_links_moved,
        "relationships_moved": relationships_moved,
    }


@router.get("/api/source-materials/{material_id}/concepts", response_model=list[SourceConceptLinkOut])
def list_source_material_concepts(
    material_id: int,
    include_rejected: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    get_material_or_404(db, material_id)
    query = db.query(SourceConcept).join(Concept).filter(SourceConcept.source_id == material_id)
    if not include_rejected:
        query = query.filter(Concept.status != "rejected")
    links = query.order_by(Concept.name, SourceConcept.id).all()
    return [source_concept_link_out(link, db) for link in links]


@router.post("/api/source-materials/{material_id}/extract-concepts", response_model=ConceptExtractionOut)
def extract_source_material_concepts(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    material = get_material_or_404(db, material_id)
    chunk_count = db.query(SourceChunk).filter_by(source_id=material.id).count()
    if chunk_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Extract source chunks before concepts")
    result = extract_concepts_for_source(db, material)
    return {
        "source_id": material.id,
        "status": "completed",
        "message": f"Extracted {result.concepts_linked} concept links.",
        "concepts_created": result.concepts_created,
        "concepts_linked": result.concepts_linked,
        "concepts": [source_concept_link_out(link, db) for link in result.links],
    }


@router.get("/api/concepts/{concept_id}/sources", response_model=list[ConceptSourceOut])
def list_concept_sources(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    get_concept_or_404(db, concept_id)
    links = (
        db.query(SourceConcept)
        .filter_by(concept_id=concept_id)
        .order_by(SourceConcept.created_at.desc(), SourceConcept.id.desc())
        .all()
    )
    return [concept_source_out(link) for link in links]


@router.get("/api/concepts/{concept_id}/evidence", response_model=list[ConceptEvidenceOut])
def list_concept_evidence(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    get_concept_or_404(db, concept_id)
    links = (
        db.query(SourceConcept)
        .filter_by(concept_id=concept_id)
        .order_by(SourceConcept.created_at.desc(), SourceConcept.id.desc())
        .all()
    )
    return [concept_evidence_out(link) for link in links]


@router.get("/api/concepts/{concept_id}/relationships", response_model=list[ConceptRelationshipOut])
def list_concept_relationships(
    concept_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    get_concept_or_404(db, concept_id)
    relationships = (
        db.query(ConceptRelationship)
        .filter(or_(ConceptRelationship.concept_a_id == concept_id, ConceptRelationship.concept_b_id == concept_id))
        .order_by(ConceptRelationship.created_at.desc(), ConceptRelationship.id.desc())
        .all()
    )
    return [relationship_out(relationship) for relationship in relationships]


@router.post("/api/concepts/{concept_id}/relationships", response_model=ConceptRelationshipOut, status_code=status.HTTP_201_CREATED)
def create_concept_relationship(
    concept_id: int,
    payload: ConceptRelationshipCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    concept_a = get_concept_or_404(db, concept_id)
    concept_b = get_concept_or_404(db, payload.concept_b_id)
    if concept_a.id == concept_b.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Concept relationship requires two concepts")
    relationship = ConceptRelationship(
        concept_a_id=concept_a.id,
        concept_b_id=concept_b.id,
        relationship_type=payload.relationship_type,
        confidence_score=payload.confidence_score,
        status=payload.status,
    )
    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return relationship_out(relationship)


@router.put("/api/concept-relationships/{relationship_id}", response_model=ConceptRelationshipOut)
def update_concept_relationship(
    relationship_id: int,
    payload: ConceptRelationshipPatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    relationship = get_relationship_or_404(db, relationship_id)
    patch = payload.model_dump(exclude_unset=True)
    if "concept_a_id" in patch and patch["concept_a_id"] is not None:
        get_concept_or_404(db, patch["concept_a_id"])
        relationship.concept_a_id = patch["concept_a_id"]
    if "concept_b_id" in patch and patch["concept_b_id"] is not None:
        get_concept_or_404(db, patch["concept_b_id"])
        relationship.concept_b_id = patch["concept_b_id"]
    if relationship.concept_a_id == relationship.concept_b_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Concept relationship requires two concepts")
    for key in ["relationship_type", "confidence_score", "status"]:
        if key in patch and patch[key] is not None:
            setattr(relationship, key, patch[key])
    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return relationship_out(relationship)


@router.delete("/api/concept-relationships/{relationship_id}")
def delete_concept_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    relationship = get_relationship_or_404(db, relationship_id)
    db.delete(relationship)
    db.commit()
    return {"ok": True}
