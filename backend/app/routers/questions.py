from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Course, Question, User
from app.routers.common import get_course_or_404, get_question_or_404
from app.schemas import QuestionCreate, QuestionPatch
from app.services.course_exporter import question_to_static
from app.services.validation_service import validate_db_question


router = APIRouter(tags=["questions"])


def find_course_for_payload(db: Session, payload: QuestionCreate) -> Course:
    if payload.course_id:
        course = db.get(Course, payload.course_id)
    elif payload.course_code:
        course = db.query(Course).filter_by(course_code=payload.course_code).one_or_none()
    else:
        course = None
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


@router.get("/api/courses/{course_code}/questions")
def list_course_questions(course_code: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    course = get_course_or_404(db, course_code)
    questions = db.query(Question).filter_by(course_id=course.id).order_by(Question.id).all()
    return [question_to_static(question) for question in questions]


@router.get("/api/questions/{question_id}")
def get_question(question_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return question_to_static(get_question_or_404(db, question_id))


@router.post("/api/questions", status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    course = find_course_for_payload(db, payload)
    question = Question(
        course_id=course.id,
        legacy_id=payload.legacy_id,
        question_type=payload.question_type,
        topic=payload.topic,
        subtopic=payload.subtopic,
        difficulty=payload.difficulty,
        oa_probability=payload.oa_probability,
        question_text=payload.question_text,
        choices_json=payload.choices,
        answer_json=payload.answer,
        explanation=payload.explanation,
        why_wrong_json=payload.why_wrong,
        memory=payload.memory,
        exam_tip=payload.exam_tip,
        status=payload.status,
        confidence=payload.confidence,
        lineage_json=payload.lineage,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question_to_static(question)


@router.patch("/api/questions/{question_id}")
def patch_question(
    question_id: str,
    payload: QuestionPatch,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    question = get_question_or_404(db, question_id)
    field_map = {
        "question_type": "question_type",
        "topic": "topic",
        "subtopic": "subtopic",
        "difficulty": "difficulty",
        "oa_probability": "oa_probability",
        "question_text": "question_text",
        "choices": "choices_json",
        "answer": "answer_json",
        "explanation": "explanation",
        "why_wrong": "why_wrong_json",
        "memory": "memory",
        "exam_tip": "exam_tip",
        "status": "status",
        "confidence": "confidence",
        "lineage": "lineage_json",
    }
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field_map[key], value)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question_to_static(question)


def set_status(question_id: str, next_status: str, db: Session) -> dict:
    question = get_question_or_404(db, question_id)
    question.status = next_status
    db.add(question)
    db.commit()
    return {"id": question.legacy_id or str(question.id), "status": question.status, "warnings": validate_db_question(question)}


@router.post("/api/questions/{question_id}/review")
def review_question(question_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "instructor"))):
    return set_status(question_id, "reviewed", db)


@router.post("/api/questions/{question_id}/verify")
def verify_question(question_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "instructor"))):
    return set_status(question_id, "verified", db)


@router.post("/api/questions/{question_id}/retire")
def retire_question(question_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "instructor"))):
    return set_status(question_id, "retired", db)
