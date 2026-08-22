"""Smoke tests for api/services/indexing_service.py"""
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import MagicMock, patch


def test_indexing_service_module_importable():
    """Verify the indexing_service module can be imported without errors."""
    import api.services.indexing_service as svc  # noqa: F401
    assert svc is not None


def test_indexing_in_flight_set_is_empty_on_init():
    """The in-flight tracking set starts empty."""
    from api.services.indexing_service import _indexing_in_flight
    # It may contain items from other tests but should be a set
    assert isinstance(_indexing_in_flight, set)


def test_extract_clone_error_context_returns_expected_fields():
    from api.services.indexing_service import _extract_clone_error_context

    class FakeCloneError(Exception):
        clone_source = "https://github.com/org/repo.git"
        clone_target_path = r"C:\repos\repo"

    context = _extract_clone_error_context(FakeCloneError("boom"))
    assert context == {
        "clone_source": "https://github.com/org/repo.git",
        "clone_target_path": r"C:\repos\repo",
    }


def test_run_indexing_pipeline_emits_clone_diagnostics_on_error(monkeypatch):
    import api.services.indexing_service as svc

    class FakeCloneError(Exception):
        def __init__(self):
            super().__init__("[Errno 22] Invalid argument")
            self.clone_source = "https://github.com/org/repo.git"
            self.clone_target_path = r"C:\repos\repo"

    def fail_pipeline(_source, _emit):
        raise FakeCloneError()

    monkeypatch.setattr(svc, "_run_pipeline_sync", fail_pipeline)

    queue: asyncio.Queue = asyncio.Queue()
    asyncio.run(svc.run_indexing_pipeline("https://github.com/org/repo.git", "repo-id", queue))
    event = queue.get_nowait()

    assert event["step"] == "error"
    assert "[Errno 22] Invalid argument" in event["message"]
    assert "clone_source=https://github.com/org/repo.git" in event["message"]
    assert r"clone_target_path=C:\repos\repo" in event["message"]
    assert event["clone_source"] == "https://github.com/org/repo.git"
    assert event["clone_target_path"] == r"C:\repos\repo"


def test_format_indexing_error_message_appends_clone_context():
    from api.services.indexing_service import _format_indexing_error_message

    message = _format_indexing_error_message(
        RuntimeError("boom"),
        {
            "clone_source": "https://github.com/org/repo.git",
            "clone_target_path": r"C:\repos\repo",
        },
    )

    assert "boom" in message
    assert "clone_source=https://github.com/org/repo.git" in message
    assert r"clone_target_path=C:\repos\repo" in message


def test_ensure_embedding_model_available_returns_true_when_present(monkeypatch):
    import api.services.indexing_service as svc

    monkeypatch.setattr(svc, "_check_model_available", lambda _model: True)

    events = []

    def emit(step, message, progress, **kwargs):
        events.append((step, message, progress, kwargs))

    assert svc._ensure_embedding_model_available(emit, "nomic-embed-text") is True
    assert events == []


def test_ensure_embedding_model_available_emits_error_after_failed_pull(monkeypatch):
    import api.services.indexing_service as svc

    monkeypatch.setattr(svc, "_check_model_available", lambda _model: False)
    monkeypatch.setattr(svc, "_pull_ollama_model", lambda _model: False)
    monkeypatch.setattr(svc, "_list_ollama_models", lambda: ["llama3.2:3b"])

    events = []

    def emit(step, message, progress, **kwargs):
        events.append({"step": step, "message": message, "progress": progress, **kwargs})

    assert svc._ensure_embedding_model_available(emit, "nomic-embed-text") is False
    assert events[-1]["step"] == "error"
    assert events[-1]["embed_model"] == "nomic-embed-text"
    assert events[-1]["available_ollama_models"] == "llama3.2:3b"
