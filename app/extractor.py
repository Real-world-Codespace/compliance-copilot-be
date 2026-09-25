from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@dataclass(slots=True)
class ExtractedPage:
    text: str
    page_number: int | None


def extract_text(data: bytes, filename: str) -> list[ExtractedPage]:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Chỉ hỗ trợ PDF có text, DOCX và TXT. Tài liệu scan cần OCR worker riêng.")
    if extension == ".pdf":
        from pypdf import PdfReader
        return [ExtractedPage((page.extract_text() or "").strip(), index) for index, page in enumerate(PdfReader(BytesIO(data)).pages, start=1)]
    if extension == ".docx":
        from docx import Document
        document = Document(BytesIO(data))
        return [ExtractedPage("\n".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()), None)]
    return [ExtractedPage(data.decode("utf-8-sig", errors="replace").strip(), None)]
