from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import MockExamSession, QuestionAttempt, ReviewNote, User, UserBookmark, UserCourseProgress
from app.routers.common import get_course_or_404, get_question_or_404
from app.schemas import AttemptCreate, MockSessionCreate, ReviewNoteCreate
from app.services.analytics_service import course_analytics, progress_summary
from app.services.course_exporter import question_public_id


router = APIRouter(tags=["progress"])


def normalize_answer(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize_answer(item) for item in value]
    if isinstance(value, dict):
        return {str(key): normalize_answer(answer) for key, answer in value.items()}
    return value


def score_answer(question, selected: Any) -> bool:
    expected = normalize_answer(question.answer_json)
    selected = normalize_answer(selected)
    if question.question_type == "multi_select" and isinstance(expected, list) and isinstance(selected, list):
        return sorted(map(str, expected)) == sorted(map(str, selected))
    return selected == expected


def recalc_user_course_progress(db: Session, user: User, course_id: int):
    attempts = db.query(QuestionAttempt).filter_by(user_id=user.id, course_id=course_id).all()
    unique_questions = {attempt.question_id for attempt in attempts}
    correct = sum(1 for attempt in attempts if attempt.is_correct)
    total = len(attempts)
    progress = db.query(UserCourseProgress).filter_by(user_id=user.id, course_id=course_id).one_or_none()
    if not progress:
        progress = UserCourseProgress(user_id=user.id, course_id=course_id)
    progress.questions_answered = len(unique_questions)
    progress.correct_answers = correct
    progress.mastery_percent = round((correct / total) * 100) if total else 0
    progress.readiness_score = progress.mastery_percent
    progress.last_studied_at = datetime.now(timezone.utc) if attempts else None
    db.add(progress)


@router.get("/api/courses/{course_code}/progress")
def get_progress(course_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = get_course_or_404(db, course_code)
    return progress_summary(db, current_user, course)


@router.post("/api/questions/{question_id}/attempt", status_code=status.HTTP_201_CREATED)
def record_attempt(
    question_id: str,
    payload: AttemptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = get_question_or_404(db, question_id)
    selected = payload.selected_answer if payload.selected_answer is not None else payload.selected_answer_json
    is_correct = payload.is_correct if payload.is_correct is not None else score_answer(question, selected)
    attempt = QuestionAttempt(
        user_id=current_user.id,
        course_id=question.course_id,
        question_id=question.id,
        selected_answer_json=selected,
        is_correct=bool(is_correct),
        time_spent_seconds=payload.time_spent_seconds,
        mode=payload.mode or "practice",
    )
    db.add(attempt)
    db.flush()
    recalc_user_course_progress(db, current_user, question.course_id)
    db.commit()
    db.refresh(attempt)
    return {
        "id": attempt.id,
        "question_id": question_public_id(question),
        "selected_answer": attempt.selected_answer_json,
        "is_correct": attempt.is_correct,
        "mode": attempt.mode,
        "attempted_at": attempt.attempted_at.isoformat(),
    }


@router.get("/api/courses/{course_code}/bookmarks")
def list_bookmarks(course_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = get_course_or_404(db, course_code)
    state = progress_summary(db, current_user, course)
    return list(state["bookmarks"].values())


@router.post("/api/questions/{question_id}/bookmark", status_code=status.HTTP_201_CREATED)
def create_bookmark(question_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    question = get_question_or_404(db, question_id)
    bookmark = db.query(UserBookmark).filter_by(user_id=current_user.id, question_id=question.id).one_or_none()
    if not bookmark:
        bookmark = UserBookmark(user_id=current_user.id, course_id=question.course_id, question_id=question.id)
        db.add(bookmark)
        db.commit()
        db.refresh(bookmark)
    return {
        "id": question_public_id(question),
        "topic": question.topic,
        "question": question.question_text,
        "date": bookmark.created_at.isoformat(),
    }


@router.delete("/api/questions/{question_id}/bookmark")
def delete_bookmark(question_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    question = get_question_or_404(db, question_id)
    bookmark = db.query(UserBookmark).filter_by(user_id=current_user.id, question_id=question.id).one_or_none()
    if bookmark:
        db.delete(bookmark)
        db.commit()
    return {"ok": True}


@router.post("/api/questions/{question_id}/review-note", status_code=status.HTTP_201_CREATED)
def save_review_note(
    question_id: str,
    payload: ReviewNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = get_question_or_404(db, question_id)
    note = (
        db.query(ReviewNote)
        .filter_by(user_id=current_user.id, question_id=question.id)
        .order_by(ReviewNote.created_at.desc())
        .first()
    )
    if not note:
        note = ReviewNote(user_id=current_user.id, question_id=question.id, note=payload.note)
    else:
        note.note = payload.note
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"ok": True, "id": note.id, "question_id": question_public_id(question), "note": note.note}


@router.get("/api/courses/{course_code}/analytics")
def analytics(course_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = get_course_or_404(db, course_code)
    return course_analytics(db, current_user, course)


@router.post("/api/courses/{course_code}/mock-sessions", status_code=status.HTTP_201_CREATED)
def record_mock_session(
    course_code: str,
    payload: MockSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = get_course_or_404(db, course_code)
    score = payload.score_percent if payload.score_percent is not None else payload.scorePct
    question_count = payload.question_count if payload.question_count is not None else payload.questionCount
    pass_estimate = payload.passed_estimate if payload.passed_estimate is not None else payload.passEstimate
    session = MockExamSession(
        user_id=current_user.id,
        course_id=course.id,
        completed_at=datetime.now(timezone.utc),
        score_percent=score,
        question_count=question_count or 0,
        passed_estimate=pass_estimate,
        breakdown_json=payload.breakdown or payload.topicBreakdown,
        answers_json={"answers": payload.answers, "review": payload.review},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "score_percent": session.score_percent}
