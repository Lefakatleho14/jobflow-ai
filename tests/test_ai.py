"""
Phase 9 tests: OllamaClient, LLMService, error handling.

All tests mock HTTP calls — they do NOT require a running Ollama instance.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from app.ai import (
    LLMResponseError,
    LLMService,
    LLMTimeoutError,
    LLMUnavailableError,
    OllamaClient,
)
from app.ai.errors import ModelNotFoundError


# ---------------------------------------------------------------- helpers

def _mock_get_response(content: bytes, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=content,
        request=httpx.Request("GET", "http://localhost:11434/api/tags"),
    )


def _mock_post_response(content: bytes, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=content,
        request=httpx.Request("POST", "http://localhost:11434/api/generate"),
    )


# ---------------------------------------------------------------- OllamaClient: list_models

@patch("app.ai.ollama_client.httpx.get")
def test_list_models_success(mock_get):
    mock_get.return_value = _mock_get_response(
        json.dumps({
            "models": [
                {"name": "llama3.2:3b"},
                {"name": "phi3:mini"},
            ]
        }).encode()
    )
    client = OllamaClient()
    assert client.list_models() == ["llama3.2:3b", "phi3:mini"]


@patch("app.ai.ollama_client.httpx.get")
def test_list_models_unavailable(mock_get):
    mock_get.side_effect = httpx.ConnectError("refused")
    client = OllamaClient()
    with pytest.raises(LLMUnavailableError):
        client.list_models()


@patch("app.ai.ollama_client.httpx.get")
def test_list_models_bad_status(mock_get):
    mock_get.return_value = _mock_get_response(b"oops", status=500)
    client = OllamaClient()
    with pytest.raises(LLMUnavailableError):
        client.list_models()


@patch("app.ai.ollama_client.httpx.get")
def test_list_models_invalid_json(mock_get):
    mock_get.return_value = _mock_get_response(b"not json")
    client = OllamaClient()
    with pytest.raises(LLMResponseError):
        client.list_models()


# ---------------------------------------------------------------- OllamaClient: generate

@patch("app.ai.ollama_client.httpx.post")
def test_generate_success(mock_post):
    mock_post.return_value = _mock_post_response(json.dumps({
        "model": "llama3.2:3b",
        "response": '{"status":"ok"}',
        "prompt_eval_count": 15,
        "eval_count": 8,
    }).encode())
    client = OllamaClient()
    result = client.generate("hello", model="llama3.2:3b")
    assert result.text == '{"status":"ok"}'
    assert result.model == "llama3.2:3b"


@patch("app.ai.ollama_client.httpx.post")
def test_generate_timeout(mock_post):
    mock_post.side_effect = httpx.TimeoutException("timeout")
    client = OllamaClient()
    with pytest.raises(LLMTimeoutError):
        client.generate("hello", model="llama3.2:3b")


@patch("app.ai.ollama_client.httpx.post")
def test_generate_unreachable(mock_post):
    mock_post.side_effect = httpx.ConnectError("refused")
    client = OllamaClient()
    with pytest.raises(LLMUnavailableError):
        client.generate("hello", model="llama3.2:3b")


@patch("app.ai.ollama_client.httpx.post")
def test_generate_404_model_not_found(mock_post):
    mock_post.return_value = _mock_post_response(b"model not found", status=404)
    client = OllamaClient()
    with pytest.raises(LLMResponseError):
        client.generate("hello", model="wrong-model")


@patch("app.ai.ollama_client.httpx.post")
def test_generate_empty_response(mock_post):
    mock_post.return_value = _mock_post_response(
        json.dumps({"response": ""}).encode()
    )
    client = OllamaClient()
    with pytest.raises(LLMResponseError):
        client.generate("hello", model="llama3.2:3b")


# ---------------------------------------------------------------- LLMService: health

@patch("app.ai.ollama_client.httpx.get")
def test_health_model_set_and_present(mock_get, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    mock_get.return_value = _mock_get_response(
        json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()
    )
    svc = LLMService()
    status = svc.health()
    assert status.available is True
    assert status.model == "llama3.2:3b"


@patch("app.ai.ollama_client.httpx.get")
def test_health_model_not_pulled(mock_get, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "some-model")
    mock_get.return_value = _mock_get_response(
        json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()
    )
    svc = LLMService()
    status = svc.health()
    assert status.available is False
    assert "pull" in status.message.lower() or "not found" in status.message.lower()


@patch("app.ai.ollama_client.httpx.get")
def test_health_model_not_configured(mock_get, monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    mock_get.return_value = _mock_get_response(
        json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()
    )
    svc = LLMService()
    status = svc.health()
    assert status.available is False
    assert "OLLAMA_MODEL" in status.message


@patch("app.ai.ollama_client.httpx.get")
def test_health_ollama_down(mock_get, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    mock_get.side_effect = httpx.ConnectError("refused")
    svc = LLMService()
    status = svc.health()
    assert status.available is False
    assert "cannot reach" in status.message.lower()


# ---------------------------------------------------------------- LLMService: generate_json

@patch("app.ai.ollama_client.httpx.get")
@patch("app.ai.ollama_client.httpx.post")
def test_generate_json_success(mock_post, mock_get, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    mock_get.return_value = _mock_get_response(
        json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()
    )
    mock_post.return_value = _mock_post_response(json.dumps({
        "response": '{"title": "Dev", "skills": ["Python"]}'
    }).encode())
    svc = LLMService()
    data = svc.generate_json("extract this")
    assert data["title"] == "Dev"
    assert data["skills"] == ["Python"]


@patch("app.ai.ollama_client.httpx.get")
@patch("app.ai.ollama_client.httpx.post")
def test_generate_json_strips_markdown_fences(mock_post, mock_get, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    mock_get.return_value = _mock_get_response(
        json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()
    )
    mock_post.return_value = _mock_post_response(json.dumps({
        "response": '```json\n{"ok": true}\n```'
    }).encode())
    svc = LLMService()
    data = svc.generate_json("test")
    assert data == {"ok": True}


@patch("app.ai.ollama_client.httpx.get")
@patch("app.ai.ollama_client.httpx.post")
def test_generate_json_rejects_non_json(mock_post, mock_get, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    mock_get.return_value = _mock_get_response(
        json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()
    )
    mock_post.return_value = _mock_post_response(json.dumps({
        "response": "I cannot do that"
    }).encode())
    svc = LLMService()
    with pytest.raises(LLMResponseError):
        svc.generate_json("test")


@patch("app.ai.ollama_client.httpx.get")
@patch("app.ai.ollama_client.httpx.post")
def test_generate_json_rejects_non_object(mock_post, mock_get, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    mock_get.return_value = _mock_get_response(
        json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()
    )
    mock_post.return_value = _mock_post_response(json.dumps({
        "response": '[1, 2, 3]'
    }).encode())
    svc = LLMService()
    with pytest.raises(LLMResponseError):
        svc.generate_json("test")


# ---------------------------------------------------------------- LLMService: require_ready

@patch("app.ai.ollama_client.httpx.get")
def test_require_ready_raises_if_no_model(mock_get, monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    mock_get.return_value = _mock_get_response(
        json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()
    )
    svc = LLMService()
    with pytest.raises(LLMUnavailableError):
        svc._require_ready()


@patch("app.ai.ollama_client.httpx.get")
def test_require_ready_raises_model_not_found(mock_get, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "missing:model")
    mock_get.return_value = _mock_get_response(
        json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()
    )
    svc = LLMService()
    with pytest.raises(ModelNotFoundError):
        svc._require_ready()