from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Course, Question, User
from app.schemas import UserOut


def user_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


def get_course_or_404(db: Session, course_code: str) -> Course:
    course = db.query(Course).filter_by(course_code=course_code).one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


def get_question_or_404(db: Session, question_id: str) -> Question:
    question = None
    if str(question_id).isdigit():
        question = db.get(Question, int(question_id))
    if not question:
        question = db.query(Question).filter_by(legacy_id=question_id).one_or_none()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question
