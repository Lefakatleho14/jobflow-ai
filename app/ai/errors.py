"""
Typed errors for the AI layer.

Every LLM-related failure maps to one of these. Downstream phases can
catch specific classes and handle them appropriately (e.g. retry on
timeout, prompt the user on model missing).
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for all AI-layer errors."""


class LLMUnavailableError(LLMError):
    """Ollama is not reachable — service down, wrong URL, or network issue."""


class ModelNotFoundError(LLMError):
    """Ollama is reachable but the requested model is not pulled."""


class LLMTimeoutError(LLMError):
    """The request to Ollama exceeded the configured timeout."""


class LLMResponseError(LLMError):
    """Ollama returned a response, but it was malformed or unusable."""


class LLMValidationError(LLMError):
    """
    Ollama's response parsed but failed schema validation (Pydantic).
    Used in Phase 10 and beyond for structured extraction.
    """