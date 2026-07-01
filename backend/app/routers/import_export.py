from pathlib import Path

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import User
from app.schemas import ImportPathRequest, JsonCoursePackImport
from app.services.course_exporter import export_course_pack
from app.services.course_importer import import_course_bundle, import_static_course_pack
from app.services.validation_service import validate_course_pack


router = APIRouter(tags=["import-export"])


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@router.post("/api/import/json-course-pack", status_code=status.HTTP_201_CREATED)
def import_json_course_pack(
    payload: JsonCoursePackImport,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    warnings = validate_course_pack(payload.bundle)
    result = import_course_bundle(db, payload.bundle)
    return {"result": result, "warnings": warnings}


@router.get("/api/export/{course_code}")
def export_course(course_code: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return export_course_pack(db, course_code)


@router.post("/api/import/legacy-static-course/{course_code}", status_code=status.HTTP_201_CREATED)
def import_legacy_static_course(
    course_code: str,
    payload: ImportPathRequest | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    source_path = Path(payload.path).resolve() if payload and payload.path else repo_root() / "data" / course_code
    result = import_static_course_pack(db, source_path)
    return {"result": result, "path": str(source_path)}
