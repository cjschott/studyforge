import hashlib
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings


ALLOWED_UPLOADS = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
    ".markdown": {"text/markdown", "text/plain", "application/octet-stream"},
    ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain", "application/octet-stream"},
}


def sanitize_filename(filename: str) -> str:
    base_name = Path(filename or "source").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", base_name).strip(".-")
    return cleaned or "source"


def validate_upload_type(filename: str, content_type: str | None) -> str:
    suffix = Path(filename).suffix.lower()
    allowed_mimes = ALLOWED_UPLOADS.get(suffix)
    if not allowed_mimes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported source file type")
    if content_type and content_type not in allowed_mimes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported source file MIME type")
    return suffix


async def read_upload(upload: UploadFile) -> tuple[bytes, str, str]:
    safe_name = sanitize_filename(upload.filename or "source")
    validate_upload_type(safe_name, upload.content_type)
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded source file is empty")
    checksum = hashlib.sha256(content).hexdigest()
    return content, safe_name, checksum


def write_original_file(content: bytes, safe_name: str, checksum: str) -> str:
    upload_dir = Path(get_settings().source_originals_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{checksum[:16]}-{safe_name}"
    stored_path = (upload_dir / stored_name).resolve()
    if upload_dir not in stored_path.parents and stored_path != upload_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid source file path")
    stored_path.write_bytes(content)
    return str(stored_path)


def stored_path_for_display(stored_path: str) -> str:
    name = Path(stored_path).name
    return f"sources/originals/{name}" if name else ""


def delete_original_file(stored_path: str) -> bool:
    upload_dir = Path(get_settings().source_originals_dir).resolve()
    target = Path(stored_path).resolve()
    if upload_dir not in target.parents:
        return False
    if not target.exists():
        return False
    target.unlink()
    return True
