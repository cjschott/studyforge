import re
from dataclasses import dataclass, field

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Concept, SourceChunk, SourceConcept, SourceMaterial


SEEDED_KEYWORDS = [
    "malware",
    "trojan",
    "worm",
    "adware",
    "logic bomb",
    "phishing",
    "social engineering",
    "kerberos",
    "encryption",
    "firewall",
    "vpn",
    "authentication",
    "authorization",
    "access control",
    "hash",
    "certificate",
    "tls",
    "acl",
    "siem",
    "ids",
    "ips",
    "zero trust",
]

KEYWORD_DISPLAY = {
    "vpn": "VPN",
    "tls": "TLS",
    "acl": "ACL",
    "siem": "SIEM",
    "ids": "IDS",
    "ips": "IPS",
}

GENERIC_HEADINGS = {
    "chapter",
    "controls",
    "introduction",
    "key terms",
    "lesson",
    "network defense",
    "objectives",
    "overview",
    "review",
    "section",
    "summary",
    "terms",
    "threats",
}

CAPITALIZED_TERM_PATTERN = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9+#./-]{2,}|[A-Z]{2,})(?:\s+(?:[A-Z][A-Za-z0-9+#./-]{2,}|[A-Z]{2,})){0,3}\b"
)
GLOSSARY_PATTERN = re.compile(r"^\s*(?:[-*]\s*)?([A-Za-z][A-Za-z0-9+/#(). -]{1,60})\s*(?::|--| - )\s+(.{8,})$")


@dataclass
class CandidateEvidence:
    chunk: SourceChunk
    evidence_text: str


@dataclass
class ConceptCandidate:
    name: str
    normalized_name: str
    description: str = ""
    confidence_score: float = 0.6
    evidences: dict[int, CandidateEvidence] = field(default_factory=dict)


@dataclass
class ConceptExtractionResult:
    concepts_created: int
    concepts_linked: int
    links: list[SourceConcept]


def normalize_concept_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9+#]+", " ", str(value or "").strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def display_name_for(normalized_name: str, fallback: str | None = None) -> str:
    if normalized_name in KEYWORD_DISPLAY:
        return KEYWORD_DISPLAY[normalized_name]
    if fallback:
        return re.sub(r"\s+", " ", fallback).strip()
    return normalized_name.title()


def normalized_confidence(value) -> str:
    if value in {"generated", "reviewed", "verified", "unverified"}:
        return value
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return "unverified"
    if numeric >= 9:
        return "verified"
    if numeric >= 6:
        return "reviewed"
    if numeric > 0:
        return "generated"
    return "unverified"


def evidence_text(chunk: SourceChunk, term: str) -> str:
    combined = "\n".join(part for part in [chunk.heading, chunk.text] if part).strip()
    compact = re.sub(r"\s+", " ", combined)
    if not compact:
        return ""
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    match = pattern.search(compact)
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


def is_likely_heading(value: str) -> bool:
    normalized = normalize_concept_name(value)
    if not normalized or normalized in GENERIC_HEADINGS:
        return False
    words = normalized.split()
    return 1 <= len(words) <= 6 and len(normalized) >= 3


def keyword_pattern(keyword: str) -> re.Pattern:
    parts = [re.escape(part) for part in keyword.split()]
    return re.compile(r"(?<![A-Za-z0-9])" + r"\s+".join(parts) + r"(?![A-Za-z0-9])", re.IGNORECASE)


KEYWORD_PATTERNS = [(keyword, keyword_pattern(keyword)) for keyword in SEEDED_KEYWORDS]


def add_candidate(
    candidates: dict[str, ConceptCandidate],
    name: str,
    chunk: SourceChunk,
    score: float,
    description: str = "",
):
    normalized = normalize_concept_name(name)
    if not normalized or len(normalized) < 3:
        return
    candidate = candidates.get(normalized)
    if not candidate:
        candidate = ConceptCandidate(
            name=display_name_for(normalized, name),
            normalized_name=normalized,
            description=description.strip()[:600],
            confidence_score=score,
        )
        candidates[normalized] = candidate
    elif description and not candidate.description:
        candidate.description = description.strip()[:600]
    candidate.confidence_score = max(candidate.confidence_score, score)
    candidate.evidences.setdefault(chunk.id, CandidateEvidence(chunk=chunk, evidence_text=evidence_text(chunk, name)))


def collect_candidates(chunks: list[SourceChunk]) -> dict[str, ConceptCandidate]:
    candidates: dict[str, ConceptCandidate] = {}
    capitalized_counts: dict[str, int] = {}
    capitalized_names: dict[str, str] = {}

    for chunk in chunks:
        if is_likely_heading(chunk.heading):
            add_candidate(candidates, chunk.heading, chunk, 0.58)

        for line in chunk.text.splitlines():
            match = GLOSSARY_PATTERN.match(line)
            if not match:
                continue
            term, description = match.groups()
            if len(term.split()) <= 6:
                add_candidate(candidates, term, chunk, 0.74, description)

        for keyword, pattern in KEYWORD_PATTERNS:
            if pattern.search(chunk.text) or pattern.search(chunk.heading or ""):
                add_candidate(candidates, display_name_for(keyword, keyword), chunk, 0.68)

        for match in CAPITALIZED_TERM_PATTERN.finditer(chunk.text):
            term = match.group(0).strip(" .,:;()[]")
            normalized = normalize_concept_name(term)
            if normalized in GENERIC_HEADINGS or len(normalized) < 3:
                continue
            capitalized_counts[normalized] = capitalized_counts.get(normalized, 0) + 1
            capitalized_names.setdefault(normalized, term)

    repeated_capitalized = {normalized for normalized, count in capitalized_counts.items() if count >= 2}
    for chunk in chunks:
        for normalized in repeated_capitalized:
            name = capitalized_names[normalized]
            if re.search(re.escape(name), chunk.text, re.IGNORECASE):
                add_candidate(candidates, name, chunk, 0.55)

    return candidates


def get_or_create_concept(db: Session, candidate: ConceptCandidate) -> tuple[Concept, bool]:
    concept = (
        db.query(Concept)
        .filter(
            or_(
                Concept.normalized_name == candidate.normalized_name,
                func.lower(Concept.name) == candidate.normalized_name,
            )
        )
        .order_by(Concept.id)
        .first()
    )
    created = concept is None
    if created:
        concept = Concept(
            name=candidate.name,
            normalized_name=candidate.normalized_name,
            description=candidate.description,
            status="generated",
            confidence="generated",
        )
    else:
        concept.normalized_name = candidate.normalized_name
        concept.confidence = normalized_confidence(concept.confidence)
        if not concept.description and candidate.description:
            concept.description = candidate.description
    db.add(concept)
    db.flush()
    return concept, created


def extract_concepts_for_source(db: Session, material: SourceMaterial) -> ConceptExtractionResult:
    chunks = db.query(SourceChunk).filter_by(source_id=material.id).order_by(SourceChunk.chunk_number).all()
    candidates = collect_candidates(chunks)
    concepts_created = 0
    concepts_linked = 0

    for candidate in candidates.values():
        concept, created = get_or_create_concept(db, candidate)
        if created:
            concepts_created += 1
        for evidence in candidate.evidences.values():
            link = (
                db.query(SourceConcept)
                .filter_by(source_chunk_id=evidence.chunk.id, concept_id=concept.id)
                .one_or_none()
            )
            if link:
                continue
            db.add(
                SourceConcept(
                    source_id=material.id,
                    source_chunk_id=evidence.chunk.id,
                    concept_id=concept.id,
                    evidence_text=evidence.evidence_text,
                    confidence_score=candidate.confidence_score,
                    extraction_method="rule_based",
                )
            )
            concepts_linked += 1

    db.commit()
    links = (
        db.query(SourceConcept)
        .join(Concept)
        .filter(SourceConcept.source_id == material.id)
        .order_by(Concept.name, SourceConcept.id)
        .all()
    )
    return ConceptExtractionResult(
        concepts_created=concepts_created,
        concepts_linked=concepts_linked,
        links=links,
    )
