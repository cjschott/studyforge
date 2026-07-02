from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import SourceChunk, SourceImportJob, SourceLibrary, SourceMaterial, User, utcnow
from app.schemas import (
    SourceChunkOut,
    SourceExtractionOut,
    SourceLibraryCreate,
    SourceLibraryOut,
    SourceLibraryPatch,
    SourceMaterialOut,
    SourceMaterialPatch,
)
from app.services.source_chunking_service import chunk_extracted_text
from app.services.source_extraction_service import extract_source_text
from app.services.source_file_service import read_upload, write_original_file


router = APIRouter(tags=["source-libraries"])

SOURCE_TYPES = {
    "official_course_material",
    "practice_assessment",
    "quiz",
    "vendor_doc",
    "nist",
    "rfc",
    "community_deck",
    "quizlet_csv",
    "anki_apkg",
    "youtube_link",
    "web_link",
    "personal_notes",
    "csv",
    "pdf",
    "docx",
    "markdown",
    "txt",
    "other",
}
CONFIDENCE_VALUES = {"verified", "reviewed", "generated", "unverified"}
VERIFICATION_VALUES = {"not_reviewed", "needs_review", "reviewed", "verified", "rejected"}
COPYRIGHT_VALUES = {"owned", "licensed", "public", "linked_only", "personal_use_only", "unknown"}


def iso(value):
    return value.isoformat() if value else None


def source_library_out(library: SourceLibrary) -> dict:
    return {
        "id": library.id,
        "name": library.name,
        "description": library.description,
        "category": library.category,
        "created_at": iso(library.created_at),
        "updated_at": iso(library.updated_at),
    }


def source_material_out(material: SourceMaterial) -> dict:
    return {
        "id": material.id,
        "library_id": material.library_id,
        "title": material.title,
        "source_type": material.source_type,
        "authority_level": material.authority_level,
        "confidence": material.confidence,
        "verification_status": material.verification_status,
        "copyright_status": material.copyright_status,
        "original_filename": material.original_filename,
        "stored_path": material.stored_path,
        "original_url": material.original_url,
        "checksum": material.checksum,
        "uploaded_by": material.uploaded_by,
        "created_at": iso(material.created_at),
        "updated_at": iso(material.updated_at),
    }


def source_chunk_out(chunk: SourceChunk) -> dict:
    return {
        "id": chunk.id,
        "source_id": chunk.source_id,
        "chunk_number": chunk.chunk_number,
        "page_number": chunk.page_number,
        "heading": chunk.heading,
        "text": chunk.text,
        "checksum": chunk.checksum,
        "created_at": iso(chunk.created_at),
    }


def get_library_or_404(db: Session, library_id: int) -> SourceLibrary:
    library = db.get(SourceLibrary, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source library not found")
    return library


def get_material_or_404(db: Session, material_id: int) -> SourceMaterial:
    material = db.get(SourceMaterial, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source material not found")
    return material


def validate_choice(value: str, allowed: set[str], field_name: str) -> str:
    if value not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field_name}")
    return value


@router.get("/api/source-libraries", response_model=list[SourceLibraryOut])
def list_source_libraries(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    libraries = db.query(SourceLibrary).order_by(SourceLibrary.name).all()
    return [source_library_out(library) for library in libraries]


@router.post("/api/source-libraries", response_model=SourceLibraryOut, status_code=status.HTTP_201_CREATED)
def create_source_library(
    payload: SourceLibraryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    library = SourceLibrary(
        name=payload.name.strip(),
        description=payload.description,
        category=payload.category,
    )
    db.add(library)
    db.commit()
    db.refresh(library)
    return source_library_out(library)


@router.get("/api/source-libraries/{library_id}", response_model=SourceLibraryOut)
def get_source_library(
    library_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return source_library_out(get_library_or_404(db, library_id))


@router.put("/api/source-libraries/{library_id}", response_model=SourceLibraryOut)
def update_source_library(
    library_id: int,
    payload: SourceLibraryPatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    library = get_library_or_404(db, library_id)
    patch = payload.model_dump(exclude_unset=True)
    for key, value in patch.items():
        if isinstance(value, str) and key == "name":
            value = value.strip()
        setattr(library, key, value)
    db.add(library)
    db.commit()
    db.refresh(library)
    return source_library_out(library)


@router.delete("/api/source-libraries/{library_id}")
def delete_source_library(
    library_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    library = get_library_or_404(db, library_id)
    db.delete(library)
    db.commit()
    return {"ok": True}


@router.get("/api/source-materials", response_model=list[SourceMaterialOut])
def list_source_materials(
    library_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(SourceMaterial)
    if library_id is not None:
        query = query.filter(SourceMaterial.library_id == library_id)
    materials = query.order_by(SourceMaterial.created_at.desc(), SourceMaterial.id.desc()).all()
    return [source_material_out(material) for material in materials]


@router.post("/api/source-materials/upload", response_model=SourceMaterialOut, status_code=status.HTTP_201_CREATED)
async def upload_source_material(
    library_id: int = Form(...),
    title: str = Form(...),
    source_type: str = Form("other"),
    authority_level: int = Form(3),
    confidence: str = Form("unverified"),
    verification_status: str = Form("not_reviewed"),
    copyright_status: str = Form("unknown"),
    original_url: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_library_or_404(db, library_id)
    validate_choice(source_type, SOURCE_TYPES, "source_type")
    validate_choice(confidence, CONFIDENCE_VALUES, "confidence")
    validate_choice(verification_status, VERIFICATION_VALUES, "verification_status")
    validate_choice(copyright_status, COPYRIGHT_VALUES, "copyright_status")
    if authority_level < 1 or authority_level > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="authority_level must be between 1 and 5")

    content, safe_name, checksum = await read_upload(file)
    duplicate = db.query(SourceMaterial).filter_by(checksum=checksum).one_or_none()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate source upload detected. Existing source material: {duplicate.title}",
        )

    stored_path = write_original_file(content, safe_name, checksum)
    material = SourceMaterial(
        library_id=library_id,
        title=title.strip() or safe_name,
        source_type=source_type,
        authority_level=authority_level,
        confidence=confidence,
        verification_status=verification_status,
        copyright_status=copyright_status,
        original_filename=safe_name,
        stored_path=stored_path,
        original_url=original_url,
        checksum=checksum,
        uploaded_by=current_user.id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return source_material_out(material)


@router.get("/api/source-materials/{material_id}", response_model=SourceMaterialOut)
def get_source_material(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return source_material_out(get_material_or_404(db, material_id))


@router.put("/api/source-materials/{material_id}", response_model=SourceMaterialOut)
def update_source_material(
    material_id: int,
    payload: SourceMaterialPatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    material = get_material_or_404(db, material_id)
    patch = payload.model_dump(exclude_unset=True)
    for field_name, allowed in {
        "source_type": SOURCE_TYPES,
        "confidence": CONFIDENCE_VALUES,
        "verification_status": VERIFICATION_VALUES,
        "copyright_status": COPYRIGHT_VALUES,
    }.items():
        if field_name in patch and patch[field_name] is not None:
            validate_choice(patch[field_name], allowed, field_name)

    for key, value in patch.items():
        if value is None:
            continue
        if key == "title":
            value = value.strip()
        setattr(material, key, value)

    db.add(material)
    db.commit()
    db.refresh(material)
    return source_material_out(material)


@router.delete("/api/source-materials/{material_id}")
def delete_source_material(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    material = get_material_or_404(db, material_id)
    db.delete(material)
    db.commit()
    return {"ok": True}


@router.post("/api/source-materials/{material_id}/extract", response_model=SourceExtractionOut)
def extract_source_material(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    material = get_material_or_404(db, material_id)
    started_at = utcnow()
    job = SourceImportJob(source_id=material.id, status="running", message="Extraction started.", started_at=started_at)
    db.add(job)
    db.flush()

    try:
        pages = extract_source_text(material.stored_path)
        chunks = chunk_extracted_text(pages)
        db.query(SourceChunk).filter_by(source_id=material.id).delete()
        for chunk in chunks:
            db.add(
                SourceChunk(
                    source_id=material.id,
                    chunk_number=chunk.chunk_number,
                    page_number=chunk.page_number,
                    heading=chunk.heading,
                    text=chunk.text,
                    checksum=chunk.checksum,
                )
            )
        job.status = "completed"
        job.message = f"Extracted {len(chunks)} chunks."
        job.finished_at = utcnow()
        db.add(job)
        db.commit()
        return {"source_id": material.id, "status": job.status, "message": job.message, "chunks": len(chunks)}
    except HTTPException as exc:
        job.status = "failed"
        job.message = str(exc.detail)
        job.finished_at = utcnow()
        db.add(job)
        db.commit()
        raise


@router.get("/api/source-materials/{material_id}/chunks", response_model=list[SourceChunkOut])
def list_source_chunks(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    get_material_or_404(db, material_id)
    chunks = db.query(SourceChunk).filter_by(source_id=material_id).order_by(SourceChunk.chunk_number).all()
    return [source_chunk_out(chunk) for chunk in chunks]
