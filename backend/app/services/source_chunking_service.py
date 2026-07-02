import hashlib
import re
from dataclasses import dataclass

from app.services.source_extraction_service import ExtractedText


@dataclass(frozen=True)
class SourceChunkData:
    chunk_number: int
    page_number: int | None
    heading: str
    text: str
    checksum: str


def _heading_for(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:255]
        if stripped:
            return stripped[:80]
    return ""


def _split_text(text: str, target_size: int = 1200) -> list[str]:
    normalized = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not normalized:
        return []

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", normalized) if paragraph.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > target_size:
            if current:
                chunks.append(current.strip())
                current = ""
            for index in range(0, len(paragraph), target_size):
                chunks.append(paragraph[index:index + target_size].strip())
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if current and len(candidate) > target_size:
            chunks.append(current.strip())
            current = paragraph
        else:
            current = candidate

    if current:
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk]


def chunk_extracted_text(pages: list[ExtractedText]) -> list[SourceChunkData]:
    chunked: list[SourceChunkData] = []
    for page in pages:
        for text in _split_text(page.text):
            checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunked.append(
                SourceChunkData(
                    chunk_number=len(chunked) + 1,
                    page_number=page.page_number,
                    heading=_heading_for(text),
                    text=text,
                    checksum=checksum,
                )
            )
    return chunked
