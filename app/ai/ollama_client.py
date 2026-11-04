"""
Low-level HTTP wrapper for the Ollama API.

Only this module knows about Ollama's HTTP protocol. Everything else
calls `OllamaClient.generate(...)` and `OllamaClient.list_models()`.

Endpoints used:
    GET  /api/tags     — list installed models
    POST /api/generate — single-shot text generation
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.ai.errors import (
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 180.0  # seconds — CPU inference can be slow


@dataclass
class GenerateResult:
    """Result of a single generation call."""
    text: str
    model: str
    duration_ms: int
    prompt_eval_count: int | None = None
    eval_count: int | None = None


class OllamaClient:
    """
    Thin HTTP client. No retries, no prompt construction, no schema validation.
    Just talks to the Ollama HTTP API and translates errors to our typed
    exceptions.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def list_models(self) -> list[str]:
        """
        Return the names of installed models. Raises LLMUnavailableError if
        Ollama is not reachable.
        """
        try:
            response = httpx.get(self._url("/api/tags"), timeout=5.0)
        except httpx.RequestError as exc:
            raise LLMUnavailableError(
                f"Cannot reach Ollama at {self.base_url}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise LLMUnavailableError(
                f"Ollama /api/tags returned {response.status_code}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"Ollama returned invalid JSON: {exc}") from exc

        models = data.get("models", [])
        return [m.get("name", "") for m in models if m.get("name")]

    def generate(
        self,
        prompt: str,
        model: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: str | None = None,
    ) -> GenerateResult:
        """
        Send a single generate request to Ollama.
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        if response_format == "json":
            payload["format"] = "json"

        start = time.perf_counter()
        try:
            response = httpx.post(
                self._url("/api/generate"),
                json=payload,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Ollama request timed out after {self.timeout}s"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMUnavailableError(
                f"Cannot reach Ollama at {self.base_url}: {exc}"
            ) from exc

        duration_ms = int((time.perf_counter() - start) * 1000)

        if response.status_code == 404:
            raise LLMResponseError(
                f"Ollama model not found: {model!r}. Run: ollama pull {model}"
            )
        if response.status_code != 200:
            raise LLMResponseError(
                f"Ollama returned HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"Ollama returned invalid JSON: {exc}") from exc

        text = data.get("response", "")
        if not text:
            raise LLMResponseError(
                "Ollama returned an empty response — check the model and prompt"
            )

        return GenerateResult(
            text=text,
            model=data.get("model", model),
            duration_ms=duration_ms,
            prompt_eval_count=data.get("prompt_eval_count"),
            eval_count=data.get("eval_count"),
        )