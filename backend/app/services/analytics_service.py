from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Course, MockExamSession, QuestionAttempt, ReviewNote, User, UserBookmark
from app.services.course_exporter import question_public_id


def progress_summary(db: Session, user: User, course: Course) -> dict:
    attempts = (
        db.query(QuestionAttempt)
        .filter_by(user_id=user.id, course_id=course.id)
        .order_by(QuestionAttempt.attempted_at.asc())
        .all()
    )
    bookmarks = db.query(UserBookmark).filter_by(user_id=user.id, course_id=course.id).all()
    mock_sessions = (
        db.query(MockExamSession)
        .filter_by(user_id=user.id, course_id=course.id)
        .order_by(MockExamSession.started_at.desc())
        .all()
    )
    review_notes = db.query(ReviewNote).filter_by(user_id=user.id).all()

    answered = {}
    missed = {}
    topic_stats = defaultdict(lambda: {"answered": 0, "correct": 0, "missed": 0})
    sessions = []

    for attempt in attempts:
        question = attempt.question
        qid = question_public_id(question)
        item = answered.setdefault(
            qid,
            {
                "attempts": 0,
                "correct": 0,
                "missed": 0,
                "topic": question.topic,
                "selected": None,
                "lastCorrect": False,
                "lastAnswered": None,
                "source": attempt.mode,
            },
        )
        item["attempts"] += 1
        item["selected"] = attempt.selected_answer_json
        item["lastCorrect"] = attempt.is_correct
        item["lastAnswered"] = attempt.attempted_at.isoformat()
        item["source"] = attempt.mode

        topic_stats[question.topic]["answered"] += 1
        if attempt.is_correct:
            item["correct"] += 1
            topic_stats[question.topic]["correct"] += 1
            missed.pop(qid, None)
        else:
            item["missed"] += 1
            topic_stats[question.topic]["missed"] += 1
            missed[qid] = {
                "id": qid,
                "topic": question.topic,
                "question": question.question_text,
                "lastMissed": attempt.attempted_at.isoformat(),
                "note": "",
            }

        sessions.append(
            {
                "type": attempt.mode,
                "questionId": qid,
                "topic": question.topic,
                "correct": attempt.is_correct,
                "date": attempt.attempted_at.isoformat(),
            }
        )

    bookmark_payload = {
        question_public_id(bookmark.question): {
            "id": question_public_id(bookmark.question),
            "topic": bookmark.question.topic,
            "question": bookmark.question.question_text,
            "date": bookmark.created_at.isoformat(),
        }
        for bookmark in bookmarks
    }

    mock_payload = [
        {
            "id": f"mock-{session.id}",
            "date": session.completed_at.isoformat() if session.completed_at else session.started_at.isoformat(),
            "scorePct": session.score_percent or 0,
            "total": session.question_count,
            "questionCount": session.question_count,
            "passEstimate": session.passed_estimate,
            "topicBreakdown": session.breakdown_json,
            "review": session.answers_json.get("review", []) if isinstance(session.answers_json, dict) else [],
        }
        for session in mock_sessions
    ]
    missed_notes = {
        question_public_id(note.question): note.note
        for note in review_notes
        if note.question.course_id == course.id
    }
    for qid, note in missed_notes.items():
        if qid in missed:
            missed[qid]["note"] = note

    return {
        "answered": answered,
        "missed": missed,
        "bookmarks": bookmark_payload,
        "reviewLater": {},
        "missedNotes": missed_notes,
        "topicStats": dict(topic_stats),
        "sessions": list(reversed(sessions[-35:])),
        "mockExams": mock_payload,
        "flashcards": {},
    }


def course_analytics(db: Session, user: User, course: Course) -> dict:
    state = progress_summary(db, user, course)
    attempts = sum(item["attempts"] for item in state["answered"].values())
    correct = sum(item["correct"] for item in state["answered"].values())
    accuracy = round((correct / attempts) * 100) if attempts else 0
    return {
        "course": course.course_code,
        "attempts": attempts,
        "correct": correct,
        "accuracy": accuracy,
        "uniqueAnswered": len(state["answered"]),
        "missedCount": len(state["missed"]),
        "bookmarkedCount": len(state["bookmarks"]),
        "topicStats": state["topicStats"],
        "mockExams": state["mockExams"],
    }
