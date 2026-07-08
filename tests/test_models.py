"""
tests/test_models.py
─────────────────────
Tests for Pydantic request/response models.
No HTTP calls — pure unit tests.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime
from pydantic import ValidationError

from api.models.repo import IndexRepoRequest, IndexRepoResponse, RepoStatusResponse, IndexProgressEvent
from api.models.chat import (
    CreateSessionRequest,
    CreateSessionResponse,
    SendMessageRequest,
    MessageResponse,
    ChatListItem,
    TokenEvent,
    MetadataEvent,
    DoneEvent,
    ErrorEvent,
    RetrievedFile,
)
from api.models.eval import RunEvalRequest, EvalSummaryResponse


# ── Repo Models ────────────────────────────────────────────────────────────────

class TestIndexRepoRequest:
    def test_valid_github_url(self):
        req = IndexRepoRequest(source="https://github.com/example/repo")
        assert req.source == "https://github.com/example/repo"

    def test_valid_local_path(self):
        req = IndexRepoRequest(source="/home/user/my-project")
        assert req.source == "/home/user/my-project"

    def test_strips_whitespace(self):
        req = IndexRepoRequest(source="  https://github.com/example/repo  ")
        assert req.source == "https://github.com/example/repo"

    def test_empty_source_raises(self):
        with pytest.raises(ValidationError):
            IndexRepoRequest(source="")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError):
            IndexRepoRequest(source="   ")

    def test_missing_source_raises(self):
        with pytest.raises(ValidationError):
            IndexRepoRequest()


class TestIndexRepoResponse:
    def test_valid(self):
        r = IndexRepoResponse(
            repo_id="abc-123",
            index_name="my-repo",
            status="indexing",
            message="Started",
        )
        assert r.repo_id == "abc-123"
        assert r.status == "indexing"

    def test_serialization(self):
        r = IndexRepoResponse(
            repo_id="abc-123",
            index_name="my-repo",
            status="ready",
            message="Done",
        )
        d = r.model_dump()
        assert d["repo_id"] == "abc-123"
        assert d["status"] == "ready"


class TestRepoStatusResponse:
    def test_optional_fields_default_none(self):
        r = RepoStatusResponse(
            id="r1",
            name="repo",
            source_url="https://github.com/x/y",
            index_name="y",
            status="indexing",
        )
        assert r.file_count is None
        assert r.node_count is None
        assert r.created_at is None

    def test_full_fields(self):
        r = RepoStatusResponse(
            id="r1",
            name="repo",
            source_url="https://github.com/x/y",
            index_name="y",
            status="ready",
            file_count=50,
            node_count=400,
            llm_provider="groq",
        )
        assert r.file_count == 50
        assert r.node_count == 400
        assert r.llm_provider == "groq"


class TestIndexProgressEvent:
    def test_valid(self):
        e = IndexProgressEvent(step="cloning", message="Cloning repo...", progress=10)
        assert e.progress == 10
        assert e.file_count is None

    def test_with_counts(self):
        e = IndexProgressEvent(step="done", message="Done!", progress=100, file_count=50, node_count=400)
        assert e.file_count == 50
        assert e.node_count == 400


# ── Chat Models ────────────────────────────────────────────────────────────────

class TestCreateSessionRequest:
    def test_valid(self):
        r = CreateSessionRequest(repo_id="repo-uuid-1")
        assert r.repo_id == "repo-uuid-1"

    def test_missing_repo_id_raises(self):
        with pytest.raises(ValidationError):
            CreateSessionRequest()


class TestCreateSessionResponse:
    def test_valid(self):
        r = CreateSessionResponse(chat_id="c1", repo_id="r1")
        assert r.chat_id == "c1"
        assert r.repo_id == "r1"


class TestSendMessageRequest:
    def test_valid(self):
        r = SendMessageRequest(query="What does the main function do?")
        assert r.query == "What does the main function do?"

    def test_query_stripped_property(self):
        r = SendMessageRequest(query="  hello world  ")
        assert r.query_stripped == "hello world"

    def test_empty_string_still_valid_model(self):
        # Pydantic doesn't reject empty string — the router does
        r = SendMessageRequest(query="")
        assert r.query == ""


class TestMessageResponse:
    def test_minimal(self):
        r = MessageResponse(
            id="msg-1",
            chat_id="chat-1",
            role="user",
            content="Hello",
        )
        assert r.role == "user"
        assert r.retrieved_files is None

    def test_with_retrieved_files(self):
        r = MessageResponse(
            id="msg-2",
            chat_id="chat-1",
            role="assistant",
            content="Here is the answer...",
            query_mode="code_lookup",
            retrieved_files=[{"path": "main.py", "score": 0.95}],
            latency_ms=500,
        )
        assert r.query_mode == "code_lookup"
        assert len(r.retrieved_files) == 1
        assert r.retrieved_files[0].path == "main.py"


class TestChatListItem:
    def test_optional_fields(self):
        item = ChatListItem(id="c1", repo_id="r1")
        assert item.title is None
        assert item.created_at is None


class TestSSEEventModels:
    def test_token_event(self):
        e = TokenEvent(content="Hello ")
        assert e.type == "token"
        assert e.content == "Hello "

    def test_done_event(self):
        e = DoneEvent()
        assert e.type == "done"

    def test_error_event(self):
        e = ErrorEvent(message="Something went wrong")
        assert e.type == "error"
        assert e.message == "Something went wrong"

    def test_metadata_event(self):
        e = MetadataEvent(
            query_mode="architectural",
            retrieved_files=[RetrievedFile(path="README.md", score=0.9)],
            latency_retrieval_ms=120,
            latency_llm_ms=800,
            latency_total_ms=950,
        )
        assert e.query_mode == "architectural"
        assert e.retrieved_files[0].path == "README.md"


# ── Eval Models ───────────────────────────────────────────────────────────────

class TestRunEvalRequest:
    def test_valid(self):
        r = RunEvalRequest(repo_id="r1", index_name="my-repo")
        assert r.repo_id == "r1"
        assert r.index_name == "my-repo"

    def test_missing_fields_raises(self):
        with pytest.raises(ValidationError):
            RunEvalRequest(repo_id="r1")  # missing index_name


class TestEvalSummaryResponse:
    def test_valid(self):
        r = EvalSummaryResponse(
            repo_id="r1",
            hit_rate=0.9,
            mrr=0.85,
            avg_faithfulness=0.8,
            avg_relevancy=0.75,
            mode_accuracy=0.95,
            avg_latency_total=1200.0,
            avg_latency_retrieval=300.0,
            avg_latency_rerank=100.0,
            avg_latency_llm=800.0,
            colbert_enabled=False,
            total_queries=10,
        )
        assert r.hit_rate == 0.9
        assert r.colbert_enabled is False
        assert r.total_queries == 10

    def test_optional_id_and_created_at(self):
        r = EvalSummaryResponse(
            repo_id="r1",
            hit_rate=0.0,
            mrr=0.0,
            avg_faithfulness=0.0,
            avg_relevancy=0.0,
            mode_accuracy=0.0,
            avg_latency_total=0.0,
            avg_latency_retrieval=0.0,
            avg_latency_rerank=0.0,
            avg_latency_llm=0.0,
            colbert_enabled=False,
            total_queries=0,
        )
        assert r.id is None
        assert r.created_at is None
