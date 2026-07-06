from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import User
from app.schemas import ImportPathRequest, JsonCoursePackImport
from app.services.course_exporter import export_course_pack, validate_course_export
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
    try:
        warnings = validate_course_pack(payload.bundle)
        result = import_course_bundle(db, payload.bundle)
    except (FileNotFoundError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Malformed import: {exc}") from exc
    return {"result": result, "warnings": warnings}


@router.get("/api/export/{course_code}")
def export_course(
    course_code: str,
    include_retired: bool = Query(default=False),
    include_drafts: bool = Query(default=False),
    include_lineage: bool = Query(default=True),
    include_review_metadata: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return export_course_pack(
        db,
        course_code,
        include_retired=include_retired,
        include_drafts=include_drafts,
        include_lineage=include_lineage,
        include_review_metadata=include_review_metadata,
    )


@router.get("/api/export/{course_code}/validate")
def validate_export_course(course_code: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return validate_course_export(db, course_code)


@router.post("/api/import/legacy-static-course/{course_code}", status_code=status.HTTP_201_CREATED)
def import_legacy_static_course(
    course_code: str,
    payload: ImportPathRequest | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "instructor")),
):
    source_path = Path(payload.path).resolve() if payload and payload.path else repo_root() / "data" / course_code
    try:
        result = import_static_course_pack(db, source_path)
    except (FileNotFoundError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Malformed import: {exc}") from exc
    return {"result": result, "path": str(source_path)}
