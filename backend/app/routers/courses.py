from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Course, User
from app.routers.common import get_course_or_404
from app.schemas import CourseCreate, CourseOut, CoursePatch


router = APIRouter(prefix="/api/courses", tags=["courses"])


def course_out(course: Course) -> dict:
    return {
        "id": course.id,
        "course_code": course.course_code,
        "name": course.name,
        "short_name": course.short_name,
        "description": course.description,
        "version": course.version,
        "exam_type": course.exam_type,
        "provider": course.provider,
        "is_active": course.is_active,
        "topics_json": course.topics_json or [],
    }


@router.get("", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    courses = db.query(Course).filter_by(is_active=True).order_by(Course.course_code).all()
    return [course_out(course) for course in courses]


@router.get("/{course_code}", response_model=CourseOut)
def get_course(course_code: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return course_out(get_course_or_404(db, course_code))


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    existing = db.query(Course).filter_by(course_code=payload.course_code).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Course code already exists")
    course = Course(
        course_code=payload.course_code,
        name=payload.name,
        short_name=payload.short_name,
        description=payload.description,
        version=payload.version,
        exam_type=payload.exam_type,
        provider=payload.provider,
        is_active=payload.is_active,
        topics_json=payload.topics,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course_out(course)


@router.patch("/{course_id}", response_model=CourseOut)
def patch_course(
    course_id: int,
    payload: CoursePatch,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    patch = payload.model_dump(exclude_unset=True)
    topics = patch.pop("topics", None)
    if topics is not None:
        course.topics_json = topics
    for key, value in patch.items():
        setattr(course, key, value)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course_out(course)


@router.delete("/{course_id}")
def retire_course(course_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "instructor"))):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    course.is_active = False
    db.add(course)
    db.commit()
    return {"ok": True, "is_active": False}
