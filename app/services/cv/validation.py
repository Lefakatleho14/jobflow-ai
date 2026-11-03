"""
File validation for CV uploads.

Checks:
    * extension is allow-listed (.pdf, .docx)
    * file size does not exceed 5 MB
    * magic bytes match the extension

We check magic bytes so a .pdf that's actually a ZIP or EXE is rejected.
"""

from __future__ import annotations

from pathlib import Path

from app.services.cv.errors import CVValidationError

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB

ALLOWED_EXTENSIONS = {".pdf", ".docx"}

# magic byte prefixes
_PDF_MAGIC = b"%PDF"
_DOCX_MAGIC = b"PK\x03\x04"  # DOCX is a ZIP container


def validate_file(path: Path) -> None:
    """
    Validate a candidate CV file. Raises CVValidationError on any problem.
    """
    if not path.is_file():
        raise CVValidationError(f"Not a file: {path}")

    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise CVValidationError(
            f"Unsupported extension {ext!r}. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )

    size = path.stat().st_size
    if size == 0:
        raise CVValidationError("File is empty")
    if size > MAX_FILE_BYTES:
        raise CVValidationError(
            f"File too large ({size} bytes). Max: {MAX_FILE_BYTES} bytes"
        )

    with path.open("rb") as fh:
        head = fh.read(8)

    if ext == ".pdf" and not head.startswith(_PDF_MAGIC):
        raise CVValidationError("File claims to be PDF but is not")
    if ext == ".docx" and not head.startswith(_DOCX_MAGIC):
        raise CVValidationError("File claims to be DOCX but is not")