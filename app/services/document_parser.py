from dataclasses import dataclass
from io import BytesIO

import fitz
from docx import Document
from fastapi import HTTPException


@dataclass
class ParsedDocument:
    filename: str
    raw_text: str
    char_count: int


def _parse_pdf(content: bytes) -> str:
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        parts = [page.get_text() for page in doc]
        return "\n".join(parts).strip()
    finally:
        doc.close()


def _parse_docx(content: bytes) -> str:
    doc = Document(BytesIO(content))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()


def parse_document(filename: str, content: bytes) -> ParsedDocument:
    if not content:
        raise HTTPException(status_code=422, detail=f"File '{filename}' is empty.")

    lower = filename.lower()
    try:
        if lower.endswith(".pdf"):
            text = _parse_pdf(content)
        elif lower.endswith(".docx"):
            text = _parse_docx(content)
        elif lower.endswith(".doc"):
            raise HTTPException(
                status_code=422,
                detail=f"File '{filename}': .doc format not supported. Please convert to .docx or PDF.",
            )
        elif lower.endswith(".txt"):
            text = content.decode("utf-8", errors="ignore").strip()
        else:
            raise HTTPException(
                status_code=422,
                detail=f"File '{filename}': unsupported format. Use PDF, DOCX, or TXT.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to parse '{filename}': {exc}"
        ) from exc

    if not text:
        raise HTTPException(
            status_code=422,
            detail=f"File '{filename}' contains no extractable text.",
        )

    return ParsedDocument(filename=filename, raw_text=text, char_count=len(text))
