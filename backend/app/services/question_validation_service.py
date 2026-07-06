import re
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    Concept,
    QuestionDraft,
    QuestionDraftWarning,
    SourceConflict,
    SourceMaterial,
)


UNRESOLVED_CONFLICT_STATUSES = {"generated", "needs_review", "reviewed"}
STOP_WORDS = {"a", "an", "the", "is", "are", "of", "to", "for", "and"}
LETTER_BY_INDEX = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


WARNING_MESSAGES = {
    "missing_stem": ("high", "Question stem is required."),
    "insufficient_choices": ("high", "Single-choice questions need at least 2 choices."),
    "missing_answer": ("high", "Correct answer is required."),
    "missing_explanation": ("medium", "Explanation is required."),
    "missing_correct_explanation": ("medium", "Explanation should state why the correct answer is correct."),
    "missing_wrong_answer_explanations": ("medium", "Explanation does not explain why each wrong answer is wrong."),
    "missing_difficulty": ("medium", "Difficulty is required."),
    "missing_oa_probability": ("medium", "OA probability is required."),
    "missing_lineage": ("high", "Question draft must be linked to source or concept lineage."),
    "rejected_source": ("high", "Linked source has been rejected."),
    "rejected_concept": ("high", "Linked concept has been rejected."),
    "unresolved_high_severity_conflict": (
        "high",
        "Linked source or concept has unresolved high-severity conflicts.",
    ),
    "duplicate_question": ("medium", "This draft looks similar to an existing question draft."),
}


def normalize_text(value: str | None) -> str:
    tokens = re.findall(r"[a-z0-9]+", str(value or "").lower())
    return " ".join(token for token in tokens if token not in STOP_WORDS)


def token_set(value: str | None) -> set[str]:
    return set(normalize_text(value).split())


def overlap_ratio(a: str | None, b: str | None) -> float:
    left = token_set(a)
    right = token_set(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left), len(right))


def warning_dict(code: str) -> dict[str, Any]:
    severity, message = WARNING_MESSAGES[code]
    return {"code": code, "severity": severity, "message": message}


def stored_warning_to_dict(warning: QuestionDraftWarning) -> dict[str, Any]:
    return {
        "id": warning.id,
        "draft_id": warning.draft_id,
        "code": warning.code,
        "severity": warning.severity,
        "message": warning.message,
        "created_at": warning.created_at.isoformat() if warning.created_at else None,
    }


def choices_for_draft(draft: QuestionDraft) -> list[str]:
    choices = draft.choices_json or []
    if isinstance(choices, list):
        return [str(choice) for choice in choices]
    if isinstance(choices, dict):
        return [str(value) for value in choices.values()]
    return []


def answer_values(draft: QuestionDraft) -> set[str]:
    answer = draft.correct_answer_json
    if answer is None:
        return set()
    if isinstance(answer, list):
        values = answer
    elif isinstance(answer, dict):
        values = list(answer.values())
    else:
        values = [answer]
    return {str(value).strip().lower() for value in values if str(value).strip()}


def is_choice_correct(choice: str, index: int, answers: set[str]) -> bool:
    letter = LETTER_BY_INDEX[index].lower() if index < len(LETTER_BY_INDEX) else ""
    return str(choice).strip().lower() in answers or letter in answers


def structured_explanation(draft: QuestionDraft) -> tuple[str, dict[str, str]]:
    data = draft.explanation_json if isinstance(draft.explanation_json, dict) else {}
    incorrect = data.get("incorrect") if isinstance(data.get("incorrect"), dict) else {}
    return str(data.get("correct") or "").strip(), {
        str(key).strip(): str(value).strip()
        for key, value in incorrect.items()
        if str(key).strip() and str(value).strip()
    }


def has_any_explanation(draft: QuestionDraft) -> bool:
    correct, incorrect = structured_explanation(draft)
    return bool(str(draft.explanation or "").strip() or correct or any(incorrect.values()))


def has_correct_explanation(draft: QuestionDraft) -> bool:
    correct, _ = structured_explanation(draft)
    if correct:
        return True
    text = str(draft.explanation or "").strip().lower()
    if not text:
        return False
    answers = answer_values(draft)
    return "correct" in text or any(answer and answer in text for answer in answers)


def has_wrong_answer_explanations(draft: QuestionDraft) -> bool:
    choices = choices_for_draft(draft)
    if len(choices) < 2:
        return True

    answers = answer_values(draft)
    wrong_choices = [(index, choice) for index, choice in enumerate(choices) if not is_choice_correct(choice, index, answers)]
    if not wrong_choices:
        return True

    _, incorrect = structured_explanation(draft)
    missing_structured = []
    for index, choice in wrong_choices:
        letter = LETTER_BY_INDEX[index] if index < len(LETTER_BY_INDEX) else ""
        aliases = {str(choice).strip(), letter, letter.lower()}
        if not any(key in incorrect for key in aliases):
            missing_structured.append(choice)
    if not missing_structured:
        return True

    text = str(draft.explanation or "").strip().lower()
    if not text or ("wrong" not in text and "incorrect" not in text):
        return False
    return all(str(choice).strip().lower() in text for _, choice in wrong_choices)


def lineage_ids(draft: QuestionDraft) -> tuple[set[int], set[int], set[int]]:
    source_ids = {draft.source_id} if draft.source_id else set()
    chunk_ids = {draft.source_chunk_id} if draft.source_chunk_id else set()
    concept_ids = {draft.concept_id} if draft.concept_id else set()
    for row in draft.lineage:
        if row.source_id:
            source_ids.add(row.source_id)
        if row.source_chunk_id:
            chunk_ids.add(row.source_chunk_id)
        if row.concept_id:
            concept_ids.add(row.concept_id)
    return source_ids, chunk_ids, concept_ids


def has_lineage(draft: QuestionDraft) -> bool:
    source_ids, chunk_ids, concept_ids = lineage_ids(draft)
    if source_ids or chunk_ids or concept_ids:
        return True
    return any(str(row.evidence_text or "").strip() for row in draft.lineage)


def has_rejected_source(db: Session, source_ids: set[int]) -> bool:
    if not source_ids:
        return False
    return (
        db.query(SourceMaterial)
        .filter(SourceMaterial.id.in_(source_ids))
        .filter(or_(SourceMaterial.confidence == "rejected", SourceMaterial.verification_status == "rejected"))
        .first()
        is not None
    )


def has_rejected_concept(db: Session, concept_ids: set[int]) -> bool:
    if not concept_ids:
        return False
    return db.query(Concept).filter(Concept.id.in_(concept_ids), Concept.status == "rejected").first() is not None


def has_unresolved_high_conflict(
    db: Session,
    source_ids: set[int],
    chunk_ids: set[int],
    concept_ids: set[int],
) -> bool:
    predicates = []
    if source_ids:
        predicates.extend([SourceConflict.source_id_a.in_(source_ids), SourceConflict.source_id_b.in_(source_ids)])
    if chunk_ids:
        predicates.extend(
            [SourceConflict.source_chunk_id_a.in_(chunk_ids), SourceConflict.source_chunk_id_b.in_(chunk_ids)]
        )
    if concept_ids:
        predicates.append(SourceConflict.concept_id.in_(concept_ids))
    if not predicates:
        return False
    return (
        db.query(SourceConflict)
        .filter(SourceConflict.severity == "high")
        .filter(SourceConflict.status.in_(UNRESOLVED_CONFLICT_STATUSES))
        .filter(or_(*predicates))
        .first()
        is not None
    )


def has_duplicate_draft(db: Session, draft: QuestionDraft) -> bool:
    normalized_stem = normalize_text(draft.stem)
    if not normalized_stem:
        return False
    candidates = (
        db.query(QuestionDraft)
        .filter(QuestionDraft.id != draft.id)
        .filter(QuestionDraft.course_code == draft.course_code)
        .filter(QuestionDraft.status != "rejected")
        .all()
    )
    for candidate in candidates:
        candidate_stem = normalize_text(candidate.stem)
        if candidate_stem == normalized_stem:
            return True
        ratio = overlap_ratio(candidate.stem, draft.stem)
        if ratio >= 0.8:
            return True
        if draft.concept_id and candidate.concept_id == draft.concept_id and ratio >= 0.6:
            return True
    return False


def validate_question_draft(db: Session, draft: QuestionDraft) -> list[dict[str, Any]]:
    codes: list[str] = []

    def add(code: str):
        if code not in codes:
            codes.append(code)

    choices = choices_for_draft(draft)
    if not str(draft.stem or "").strip():
        add("missing_stem")
    if draft.question_type == "single_choice" and len(choices) < 2:
        add("insufficient_choices")
    if not answer_values(draft):
        add("missing_answer")
    if not has_any_explanation(draft):
        add("missing_explanation")
    elif not has_correct_explanation(draft):
        add("missing_correct_explanation")
    if not has_wrong_answer_explanations(draft):
        add("missing_wrong_answer_explanations")
    if draft.difficulty is None:
        add("missing_difficulty")
    if draft.oa_probability is None:
        add("missing_oa_probability")
    if not has_lineage(draft):
        add("missing_lineage")

    source_ids, chunk_ids, concept_ids = lineage_ids(draft)
    if has_rejected_source(db, source_ids):
        add("rejected_source")
    if has_rejected_concept(db, concept_ids):
        add("rejected_concept")
    if has_unresolved_high_conflict(db, source_ids, chunk_ids, concept_ids):
        add("unresolved_high_severity_conflict")
    if has_duplicate_draft(db, draft):
        add("duplicate_question")

    return [warning_dict(code) for code in codes]


def refresh_question_draft_warnings(db: Session, draft: QuestionDraft) -> list[QuestionDraftWarning]:
    warnings = validate_question_draft(db, draft)
    existing = (
        db.query(QuestionDraftWarning)
        .filter(QuestionDraftWarning.draft_id == draft.id)
        .order_by(QuestionDraftWarning.id)
        .all()
    )
    rows: list[QuestionDraftWarning] = []
    for index, warning in enumerate(warnings):
        row = existing[index] if index < len(existing) else QuestionDraftWarning(draft_id=draft.id)
        row.code = warning["code"]
        row.severity = warning["severity"]
        row.message = warning["message"]
        db.add(row)
        rows.append(row)
    for row in existing[len(warnings) :]:
        db.delete(row)
    db.flush()
    db.expire(draft, ["warnings"])
    return rows


def stored_warnings_for_draft(draft: QuestionDraft) -> list[dict[str, Any]]:
    return [stored_warning_to_dict(warning) for warning in draft.warnings]


def high_severity_warnings(warnings: list[QuestionDraftWarning] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for warning in warnings:
        if isinstance(warning, QuestionDraftWarning):
            item = stored_warning_to_dict(warning)
        else:
            item = warning
        if item.get("severity") == "high":
            result.append(item)
    return result
