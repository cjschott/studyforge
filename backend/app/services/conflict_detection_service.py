import re
from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Concept, SourceChunk, SourceConcept, SourceConflict, SourceMaterial
from app.services.concept_extraction_service import normalize_concept_name


OLD_EXAM_PATTERN = re.compile(r"\bSY0-(?:501|601)\b", re.IGNORECASE)
ANSWER_KEY_PATTERN = re.compile(
    r"\b(?:answer\s*key|correct\s+answer|answer\s*:|correct\s*:|answers?\s*[-:]\s*[A-D])\b",
    re.IGNORECASE,
)
UNRESOLVED_STATUSES = {"generated", "needs_review", "reviewed"}


@dataclass
class ConflictDetectionResult:
    conflicts_created: int
    conflicts: list[SourceConflict]


def evidence_snippet(text: str, pattern: re.Pattern | None = None) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if not compact:
        return ""
    match = pattern.search(compact) if pattern else None
    if not match:
        return compact[:500]
    start = max(0, match.start() - 180)
    end = min(len(compact), match.end() + 300)
    snippet = compact[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(compact):
        snippet = f"{snippet}..."
    return snippet[:500]


def find_existing_conflict(
    db: Session,
    *,
    conflict_type: str,
    concept_id: int | None = None,
    source_id_a: int | None = None,
    source_chunk_id_a: int | None = None,
    source_id_b: int | None = None,
    source_chunk_id_b: int | None = None,
) -> SourceConflict | None:
    return (
        db.query(SourceConflict)
        .filter(
            SourceConflict.conflict_type == conflict_type,
            SourceConflict.concept_id.is_(concept_id) if concept_id is None else SourceConflict.concept_id == concept_id,
            SourceConflict.source_id_a.is_(source_id_a) if source_id_a is None else SourceConflict.source_id_a == source_id_a,
            SourceConflict.source_chunk_id_a.is_(source_chunk_id_a)
            if source_chunk_id_a is None
            else SourceConflict.source_chunk_id_a == source_chunk_id_a,
            SourceConflict.source_id_b.is_(source_id_b) if source_id_b is None else SourceConflict.source_id_b == source_id_b,
            SourceConflict.source_chunk_id_b.is_(source_chunk_id_b)
            if source_chunk_id_b is None
            else SourceConflict.source_chunk_id_b == source_chunk_id_b,
            SourceConflict.status.in_(UNRESOLVED_STATUSES),
        )
        .one_or_none()
    )


def add_conflict(
    db: Session,
    created: list[SourceConflict],
    *,
    conflict_type: str,
    summary: str,
    severity: str = "medium",
    concept_id: int | None = None,
    source_id_a: int | None = None,
    source_chunk_id_a: int | None = None,
    source_id_b: int | None = None,
    source_chunk_id_b: int | None = None,
    evidence_a: str = "",
    evidence_b: str = "",
    status: str = "needs_review",
):
    existing = find_existing_conflict(
        db,
        conflict_type=conflict_type,
        concept_id=concept_id,
        source_id_a=source_id_a,
        source_chunk_id_a=source_chunk_id_a,
        source_id_b=source_id_b,
        source_chunk_id_b=source_chunk_id_b,
    )
    if existing:
        created.append(existing)
        return existing, False
    conflict = SourceConflict(
        concept_id=concept_id,
        source_id_a=source_id_a,
        source_chunk_id_a=source_chunk_id_a,
        source_id_b=source_id_b,
        source_chunk_id_b=source_chunk_id_b,
        conflict_type=conflict_type,
        summary=summary,
        evidence_a=evidence_a[:500],
        evidence_b=evidence_b[:500],
        severity=severity,
        status=status,
        detection_method="rule_based",
    )
    db.add(conflict)
    db.flush()
    created.append(conflict)
    return conflict, True


def is_unverified_or_low_authority(material: SourceMaterial) -> bool:
    return (
        material.authority_level <= 2
        or material.confidence == "unverified"
        or material.verification_status in {"not_reviewed", "needs_review", "rejected"}
        or material.source_type in {"community_deck", "quizlet_csv", "web_link", "personal_notes"}
    )


def detect_conflicts_for_source(db: Session, material: SourceMaterial) -> ConflictDetectionResult:
    conflicts: list[SourceConflict] = []
    created_count = 0
    chunks = db.query(SourceChunk).filter_by(source_id=material.id).order_by(SourceChunk.chunk_number).all()

    if is_unverified_or_low_authority(material):
        _, created = add_conflict(
            db,
            conflicts,
            conflict_type="low_authority_source",
            source_id_a=material.id,
            summary=f"Source '{material.title}' is unverified, low-authority, or community-derived.",
            evidence_a=f"authority={material.authority_level}; confidence={material.confidence}; verification={material.verification_status}; type={material.source_type}",
            severity="low",
        )
        created_count += int(created)

    for chunk in chunks:
        old_exam = OLD_EXAM_PATTERN.search(chunk.text)
        if old_exam:
            _, created = add_conflict(
                db,
                conflicts,
                conflict_type="outdated_reference",
                source_id_a=material.id,
                source_chunk_id_a=chunk.id,
                summary=f"Source chunk references legacy exam version {old_exam.group(0)}.",
                evidence_a=evidence_snippet(chunk.text, OLD_EXAM_PATTERN),
                severity="high",
            )
            created_count += int(created)

        if material.verification_status != "verified" and ANSWER_KEY_PATTERN.search(chunk.text):
            _, created = add_conflict(
                db,
                conflicts,
                conflict_type="possible_bad_answer",
                source_id_a=material.id,
                source_chunk_id_a=chunk.id,
                summary="Unverified source chunk contains answer-key-like text.",
                evidence_a=evidence_snippet(chunk.text, ANSWER_KEY_PATTERN),
                severity="medium",
            )
            created_count += int(created)

    db.commit()
    for conflict in conflicts:
        db.refresh(conflict)
    return ConflictDetectionResult(conflicts_created=created_count, conflicts=conflicts)


def detect_conflicts_for_concept(db: Session, concept: Concept) -> ConflictDetectionResult:
    conflicts: list[SourceConflict] = []
    created_count = 0
    normalized = concept.normalized_name or normalize_concept_name(concept.name)
    compact = normalized.replace(" ", "")
    duplicates = (
        db.query(Concept)
        .filter(Concept.id != concept.id)
        .filter(
            or_(
                Concept.normalized_name == normalized,
                Concept.normalized_name == compact,
                Concept.name.ilike(concept.name),
            )
        )
        .order_by(Concept.id)
        .all()
    )
    for duplicate in duplicates:
        _, created = add_conflict(
            db,
            conflicts,
            conflict_type="duplicate_concept",
            concept_id=concept.id,
            summary=f"Concept '{concept.name}' may duplicate '{duplicate.name}'.",
            evidence_a=f"{concept.id}: {concept.name} ({normalized})",
            evidence_b=f"{duplicate.id}: {duplicate.name} ({duplicate.normalized_name})",
            severity="medium",
        )
        created_count += int(created)

    links = db.query(SourceConcept).filter_by(concept_id=concept.id).all()
    if not links:
        _, created = add_conflict(
            db,
            conflicts,
            conflict_type="missing_lineage",
            concept_id=concept.id,
            summary=f"Concept '{concept.name}' has no linked source chunks.",
            evidence_a=concept.description or concept.name,
            severity="low",
        )
        created_count += int(created)
    else:
        authorities = [link.source.authority_level for link in links if link.source]
        if authorities and max(authorities) - min(authorities) >= 3:
            low_link = min((link for link in links if link.source), key=lambda item: item.source.authority_level)
            high_link = max((link for link in links if link.source), key=lambda item: item.source.authority_level)
            _, created = add_conflict(
                db,
                conflicts,
                conflict_type="low_authority_source",
                concept_id=concept.id,
                source_id_a=low_link.source_id,
                source_chunk_id_a=low_link.source_chunk_id,
                source_id_b=high_link.source_id,
                source_chunk_id_b=high_link.source_chunk_id,
                summary=f"Concept '{concept.name}' is supported by sources with very different authority levels.",
                evidence_a=f"{low_link.source.title}: authority {low_link.source.authority_level}",
                evidence_b=f"{high_link.source.title}: authority {high_link.source.authority_level}",
                severity="medium",
            )
            created_count += int(created)

        if concept.status == "verified":
            for link in links:
                if link.source and is_unverified_or_low_authority(link.source):
                    _, created = add_conflict(
                        db,
                        conflicts,
                        conflict_type="unsupported_claim",
                        concept_id=concept.id,
                        source_id_a=link.source_id,
                        source_chunk_id_a=link.source_chunk_id,
                        summary=f"Verified concept '{concept.name}' is linked to unverified or low-authority source evidence.",
                        evidence_a=link.evidence_text,
                        severity="medium",
                    )
                    created_count += int(created)

    db.commit()
    for conflict in conflicts:
        db.refresh(conflict)
    return ConflictDetectionResult(conflicts_created=created_count, conflicts=conflicts)
