"""CV-related exceptions."""

from __future__ import annotations


class CVError(Exception):
    """Base CV operation failure."""


class CVValidationError(CVError):
    """File fails validation (size, type, magic bytes)."""


class CVExtractionError(CVError):
    """Text extraction from a valid file failed."""