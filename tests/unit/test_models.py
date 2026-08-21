"""
tests/test_models.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Tests for Pydantic request/response models.
No HTTP calls â€” pure unit tests.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import datetime
from pydantic import ValidationError

from api.models.repo import IndexRepoRequest, IndexRepoResponse, RepoStatusResponse, IndexProgressEvent
from api.models.chat import (
    AttachmentCreateRequest,
    AttachmentResponse,
    ConversationSummaryResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    DoneEvent,
    ErrorEvent,
    ExportResponse,
    ChatListItem,
    MessageResponse,
    RetrievedFile,
    SavedReportCreateRequest,
    SavedReportResponse,
    SendMessageRequest,
    TokenEvent,
    MetadataEvent,
    format_repository_anchor,
    build_repository_memory_context,
)
from api.models.eval import RunEvalRequest, EvalSummaryResponse


def _build_eval_summary(**overrides):
    payload = {
        "repo_id": "r1",
        "hit_rate": 0.9,
        "mrr": 0.85,
        "avg_faithfulness": 0.8,
        "avg_relevancy": 0.75,
        "mode_accuracy": 0.95,
        "avg_latency_total": 1200.0,
        "avg_latency_retrieval": 300.0,
        "avg_latency_rerank": 100.0,
        "avg_latency_llm": 800.0,
        "colbert_enabled": False,
        "total_queries": 10,
    }
    payload.update(overrides)
    return EvalSummaryResponse(**payload)


# â”€â”€ Repo Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ Chat Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestCreateSessionRequest:
    def test_valid(self):
        r = CreateSessionRequest(repo_id="repo-uuid-1")
        assert r.repo_id == "repo-uuid-1"
        assert r.session_type == "quick_ask"

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
        # Pydantic doesn't reject empty string â€” the router does
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
            retrieved_files=[{"path": "main.py", "score": 0.95, "line_start": 21, "line_end": 34}],
            latency_ms=500,
        )
        assert r.query_mode == "code_lookup"
        assert len(r.retrieved_files) == 1
        assert r.retrieved_files[0].path == "main.py"
        assert r.retrieved_files[0].line_start == 21


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


class TestConversationSummaryResponse:
    def test_valid_summary_shape(self):
        summary = ConversationSummaryResponse(
            chat_id="c1",
            repo_id="r1",
            user_id="u1",
            executive_summary="Auth flow discussion",
            technical_summary="Touched middleware and JWT service",
            key_decisions=["Use JWT for API auth."],
            action_items=["Add token expiry tests."],
            risks_identified=["Missing refresh token validation."],
            files_discussed=["api/dependencies.py"],
            services_discussed=["AuthService"],
            modules_discussed=["api/routers/chat.py"],
            classes_discussed=["ChatSessionService"],
            apis_discussed=["/api/chat/session"],
            tags=["security", "jwt"],
            keywords=["authentication", "token"],
        )
        assert summary.chat_id == "c1"
        assert "security" in summary.tags

    def test_memory_anchor_context_helpers(self):
        item = {
            "title": "Auth review",
            "executive_summary": "Token verification path",
            "files_discussed": ["api/dependencies.py"],
            "services_discussed": ["AuthService"],
            "apis_discussed": ["/api/chat/session"],
        }
        line = format_repository_anchor(item)
        assert line.startswith("- Auth review: Token verification path")

        context = build_repository_memory_context([item], current_context="USER: hi")
        assert "CURRENT CONVERSATION CONTEXT:" in context
        assert "REPOSITORY KNOWLEDGE ANCHORS:" in context


class TestExportResponse:
    def test_export_payload_model(self):
        payload = ExportResponse(
            filename="repo-memory.md",
            format="md",
            content_type="text/markdown",
            content="# test",
            meta={"session_count": 1},
        )
        assert payload.format == "md"
        assert payload.meta["session_count"] == 1


class TestAttachmentModels:
    def test_attachment_create(self):
        req = AttachmentCreateRequest(
            filename="diagram.png",
            storage_path="repos/r1/chats/c1/diagram.png",
            mime_type="image/png",
            file_size=1024,
        )
        assert req.filename.endswith(".png")

    def test_attachment_response(self):
        resp = AttachmentResponse(
            id="att-1",
            chat_id="c1",
            user_id="u1",
            filename="a.txt",
            storage_path="x/a.txt",
        )
        assert resp.chat_id == "c1"


class TestSavedReportModels:
    def test_saved_report_create(self):
        req = SavedReportCreateRequest(
            report_type="security_review",
            title="Auth Findings",
            content={"risk": "missing validation"},
        )
        assert req.report_type == "security_review"

    def test_saved_report_response(self):
        resp = SavedReportResponse(
            id="rep-1",
            repo_id="r1",
            user_id="u1",
            report_type="architecture",
            content={"summary": "ok"},
        )
        assert resp.repo_id == "r1"


# â”€â”€ Eval Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        r = _build_eval_summary()
        assert r.hit_rate == 0.9
        assert r.colbert_enabled is False
        assert r.total_queries == 10

    def test_optional_id_and_created_at(self):
        r = _build_eval_summary(
            hit_rate=0.0,
            mrr=0.0,
            avg_faithfulness=0.0,
            avg_relevancy=0.0,
            mode_accuracy=0.0,
            avg_latency_total=0.0,
            avg_latency_retrieval=0.0,
            avg_latency_rerank=0.0,
            avg_latency_llm=0.0,
            total_queries=0,
        )
        assert r.id is None
        assert r.created_at is None
