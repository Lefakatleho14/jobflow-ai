"""AI layer: Ollama client, LLM service, prompt templates."""

from app.ai.errors import (
    LLMError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMValidationError,
    ModelNotFoundError,
)
from app.ai.llm_service import HealthStatus, LLMService
from app.ai.ollama_client import GenerateResult, OllamaClient

__all__ = [
    "GenerateResult",
    "HealthStatus",
    "LLMError",
    "LLMResponseError",
    "LLMService",
    "LLMTimeoutError",
    "LLMUnavailableError",
    "LLMValidationError",
    "ModelNotFoundError",
    "OllamaClient",
]