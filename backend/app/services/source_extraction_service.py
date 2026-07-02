import csv
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status


@dataclass(frozen=True)
class ExtractedText:
    text: str
    page_number: int | None = None


def _read_text(path: Path) -> list[ExtractedText]:
    return [ExtractedText(path.read_text(encoding="utf-8", errors="replace"))]


def _read_csv(path: Path) -> list[ExtractedText]:
    rows: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            values = [value.strip() for value in row if value and value.strip()]
            if values:
                rows.append(" ".join(values))
    return [ExtractedText("\n".join(rows))]


def _read_docx(path: Path) -> list[ExtractedText]:
    try:
        from docx import Document
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="DOCX extraction dependency is not installed") from exc

    document = Document(path)
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return [ExtractedText("\n".join(paragraphs))]


def _read_pdf(path: Path) -> list[ExtractedText]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="PDF extraction dependency is not installed") from exc

    reader = PdfReader(str(path))
    pages: list[ExtractedText] = []
    for index, page in enumerate(reader.pages, start=1):
        pages.append(ExtractedText(page.extract_text() or "", page_number=index))
    return pages


def extract_source_text(stored_path: str) -> list[ExtractedText]:
    path = Path(stored_path).resolve()
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored source file not found")

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return _read_text(path)
    if suffix == ".csv":
        return _read_csv(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".pdf":
        return _read_pdf(path)

    # TODO: Add PPTX, Anki APKG, HTML, and OCR-backed image extraction in a later AI ingestion pass.
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported source file type for extraction")
