from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import DATABASE_URL, get_db
from app.models import Course, Question, QuestionAttempt, User


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/health")
def health():
    return {"ok": True, "service": "studyforge-api", "database": DATABASE_URL}


@router.get("/db-stats")
def db_stats(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    return {
        "users": db.query(func.count(User.id)).scalar() or 0,
        "courses": db.query(func.count(Course.id)).scalar() or 0,
        "questions": db.query(func.count(Question.id)).scalar() or 0,
        "attempts": db.query(func.count(QuestionAttempt.id)).scalar() or 0,
    }
