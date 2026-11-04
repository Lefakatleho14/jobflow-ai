"""
LLMService — the domain-level interface to Ollama.

Wraps OllamaClient with:
    * health checks
    * model validation
    * env-based configuration
    * typed error mapping

Downstream phases call LLMService methods. They never touch OllamaClient.

Note: this class does NOT call `load_dotenv()`. That is the responsibility
of the process entry point (main.py, CLI scripts, FastAPI startup).
Reading from `os.environ` directly keeps the service testable — tests can
use `monkeypatch.setenv` / `monkeypatch.delenv` without fighting a
re-load of the .env file on every instantiation.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from app.ai.errors import (
    LLMError,
    LLMResponseError,
    LLMUnavailableError,
    ModelNotFoundError,
)
from app.ai.ollama_client import DEFAULT_BASE_URL, OllamaClient
from app.ai.prompt_templates import (
    SYSTEM_SAFE_EXTRACTION,
    job_requirement_extraction_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    available: bool
    base_url: str
    model: str | None
    models_available: list[str]
    message: str


def _env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is None or value == "":
        return default
    return value


class LLMService:
    """
    Domain interface to Ollama.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = base_url or _env("OLLAMA_BASE_URL", DEFAULT_BASE_URL)
        self.model = model or _env("OLLAMA_MODEL", None)

        # Read timeout from env if not explicitly passed.
        if timeout is None:
            raw_timeout = _env("OLLAMA_TIMEOUT", "180")
            try:
                timeout = float(raw_timeout) if raw_timeout else 180.0
            except ValueError:
                timeout = 180.0

        self.client = OllamaClient(base_url=self.base_url, timeout=timeout)

    # ---- Health ----

    def health(self) -> HealthStatus:
        """
        Check Ollama availability and model presence.
        Returns a HealthStatus; does not raise.
        """
        try:
            models = self.client.list_models()
        except LLMUnavailableError as exc:
            return HealthStatus(
                available=False,
                base_url=self.base_url,
                model=self.model,
                models_available=[],
                message=str(exc),
            )

        if not self.model:
            return HealthStatus(
                available=False,
                base_url=self.base_url,
                model=None,
                models_available=models,
                message="OLLAMA_MODEL is not set in .env",
            )

        # Model names in Ollama include tags (e.g. "llama3.2:3b").
        # Match either the exact string or the base name.
        model_present = any(
            m == self.model or m.split(":")[0] == self.model.split(":")[0]
            for m in models
        )

        if not model_present:
            return HealthStatus(
                available=False,
                base_url=self.base_url,
                model=self.model,
                models_available=models,
                message=(
                    f"Model {self.model!r} not found. "
                    f"Available: {models or '(none)'}. "
                    f"Run: ollama pull {self.model}"
                ),
            )

        return HealthStatus(
            available=True,
            base_url=self.base_url,
            model=self.model,
            models_available=models,
            message="OK",
        )

    def _require_ready(self) -> None:
        """Raise a typed error if the service is not ready."""
        if not self.model:
            raise LLMUnavailableError("OLLAMA_MODEL is not set in .env")
        try:
            self.client.list_models()
        except LLMUnavailableError:
            raise
        # Actually check the model is present.
        status = self.health()
        if not status.available:
            if status.model and status.model not in str(status.models_available):
                raise ModelNotFoundError(status.message)
            raise LLMUnavailableError(status.message)

    # ---- Generation ----

    def ping(self) -> str:
        """Send a minimal prompt and verify the response is sensible."""
        from app.ai.prompt_templates import health_probe_prompt

        self._require_ready()
        assert self.model is not None
        result = self.client.generate(
            prompt=health_probe_prompt(),
            model=self.model,
            temperature=0.0,
            max_tokens=30,
            response_format="json",
        )
        return result.text

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = 1500,
    ) -> dict:
        """
        Generate structured JSON output.
        Enforces Ollama JSON mode, strips markdown fences if present,
        and raises LLMResponseError on unparseable output.
        """
        self._require_ready()
        assert self.model is not None

        result = self.client.generate(
            prompt=prompt,
            model=self.model,
            system=system or SYSTEM_SAFE_EXTRACTION,
            temperature=0.0,
            max_tokens=max_tokens,
            response_format="json",
        )

        text = result.text.strip()

        # Some models wrap JSON in ```json ... ``` fences despite format=json.
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                f"Model returned non-JSON output: {text[:200]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise LLMResponseError(
                f"Expected JSON object, got {type(data).__name__}"
            )

        return data

    # ---- Requirement extraction (Phase 9 scaffolding; full use in Phase 10) ----

    def extract_job_requirements(self, job_description: str) -> dict:
        """
        Extract structured requirements from a job description.
        Returns the raw dict. Validation against the JobRequirement model
        happens in Phase 10.
        """
        prompt = job_requirement_extraction_prompt(job_description)
        return self.generate_json(
            prompt=prompt,
            system=SYSTEM_SAFE_EXTRACTION,
            max_tokens=1500,
        )