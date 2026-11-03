"""
Text extraction from PDF and DOCX.

Returns plain text with basic whitespace normalization.
No layout preservation — we only need text for downstream extraction.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from app.services.cv.errors import CVExtractionError

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"[ \t]+")
_MULTI_NL = re.compile(r"\n{3,}")


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    text = _MULTI_NL.sub("\n\n", text)
    return text.strip()


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise CVExtractionError("pypdf is not installed") from exc

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            # Try with empty password; many CVs are "encrypted" but readable.
            try:
                reader.decrypt("")
            except Exception as exc:
                raise CVExtractionError("PDF is password-protected") from exc

        pages: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                logger.warning("Failed to extract page %d: %s", i, exc)
                continue
            if text.strip():
                pages.append(text)
        if not pages:
            raise CVExtractionError("No extractable text found in PDF")
        return _normalize_text("\n\n".join(pages))
    except CVExtractionError:
        raise
    except Exception as exc:
        raise CVExtractionError(f"PDF extraction failed: {exc}") from exc


def extract_docx_text(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise CVExtractionError("python-docx is not installed") from exc

    try:
        doc = Document(str(path))
        parts: list[str] = []
        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text)
        if not parts:
            raise CVExtractionError("No extractable text found in DOCX")
        return _normalize_text("\n".join(parts))
    except CVExtractionError:
        raise
    except Exception as exc:
        raise CVExtractionError(f"DOCX extraction failed: {exc}") from exc


def extract_text(path: Path) -> str:
    """Dispatch on extension. Assumes `validate_file` has already passed."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf_text(path)
    if ext == ".docx":
        return extract_docx_text(path)
    raise CVExtractionError(f"Cannot extract text from {ext!r}")