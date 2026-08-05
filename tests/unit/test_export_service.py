"""
Unit tests for api/services/export_service.py

Covers:
- _render_markdown: structure, sessions, messages
- _render_plain_text: strips markdown symbols
- _render_pdf_bytes: returns valid PDF bytes
- _render_docx_bytes: returns valid ZIP/OOXML bytes
- build_export_payload: all supported formats (md, txt, json, pdf, docx)
- Negative paths: unsupported format raises ValueError, empty sessions
"""

from __future__ import annotations

import base64
import json
import zipfile

import pytest


# ─── Test fixtures ──────────────────────────────────────────────────────────

def _make_session(
    session_id="s-1",
    title="Test Session",
    messages=None,
    summary=None,
):
    default_messages = [
        {
            "role": "user",
            "content": "How does indexing work?",
            "created_at": "2026-01-01T00:00:01Z",
            "query_mode": None,
            "latency_ms": None,
            "retrieved_files": [],
        },
        {
            "role": "assistant",
            "content": "Indexing uses LlamaIndex.",
            "created_at": "2026-01-01T00:00:02Z",
            "query_mode": "code_lookup",
            "latency_ms": 120,
            "retrieved_files": ["api/main.py"],
        },
    ]
    return {
        "id": session_id,
        "title": title,
        "session_type": "quick_ask",
        "updated_at": "2026-01-01T00:00:00Z",
        "messages": default_messages if messages is None else messages,
        "summary": summary or {},
    }


def _call_export(format_name, sessions=None):
    from api.services.export_service import build_export_payload
    _sessions = [_make_session()] if sessions is None else sessions
    return build_export_payload(repo_name="myrepo", format_name=format_name, sessions=_sessions)


# ─── _render_markdown ───────────────────────────────────────────────────────

class TestRenderMarkdown:
    def test_contains_repo_name(self):
        from api.services.export_service import _render_markdown
        result = _render_markdown("myrepo", [_make_session()])
        assert "myrepo" in result

    def test_contains_session_title(self):
        from api.services.export_service import _render_markdown
        result = _render_markdown("r", [_make_session(title="My Chat")])
        assert "My Chat" in result

    def test_contains_message_content(self):
        from api.services.export_service import _render_markdown
        result = _render_markdown("r", [_make_session()])
        assert "How does indexing work?" in result
        assert "Indexing uses LlamaIndex." in result

    def test_empty_sessions_returns_header(self):
        from api.services.export_service import _render_markdown
        result = _render_markdown("myrepo", [])
        assert "myrepo" in result

    def test_session_with_no_messages(self):
        from api.services.export_service import _render_markdown
        session = _make_session(messages=[])
        result = _render_markdown("r", [session])
        assert "persisted messages" in result.lower() or "No persisted" in result

    def test_summary_section_included(self):
        from api.services.export_service import _render_markdown
        session = _make_session(
            summary={"executive_summary": "great code", "technical_summary": "tech notes"}
        )
        result = _render_markdown("r", [session])
        assert "great code" in result

    def test_latency_metadata_shown(self):
        from api.services.export_service import _render_markdown
        result = _render_markdown("r", [_make_session()])
        assert "120" in result  # latency_ms


# ─── _render_plain_text ─────────────────────────────────────────────────────

class TestRenderPlainText:
    def test_strips_hash_symbols(self):
        from api.services.export_service import _render_plain_text
        result = _render_plain_text("r", [_make_session()])
        assert "#" not in result

    def test_strips_backticks(self):
        from api.services.export_service import _render_plain_text
        result = _render_plain_text("r", [_make_session()])
        assert "`" not in result

    def test_contains_content(self):
        from api.services.export_service import _render_plain_text
        result = _render_plain_text("r", [_make_session()])
        assert "Indexing uses LlamaIndex." in result


# ─── _render_pdf_bytes ──────────────────────────────────────────────────────

class TestRenderPdfBytes:
    def test_starts_with_pdf_header(self):
        from api.services.export_service import _render_pdf_bytes
        data = _render_pdf_bytes("testrepo", [_make_session()])
        assert data.startswith(b"%PDF-")

    def test_ends_with_eof(self):
        from api.services.export_service import _render_pdf_bytes
        data = _render_pdf_bytes("testrepo", [_make_session()])
        assert b"%%EOF" in data

    def test_returns_bytes(self):
        from api.services.export_service import _render_pdf_bytes
        assert isinstance(_render_pdf_bytes("r", []), bytes)

    def test_empty_sessions(self):
        from api.services.export_service import _render_pdf_bytes
        data = _render_pdf_bytes("r", [])
        assert data.startswith(b"%PDF-")


# ─── _render_docx_bytes ─────────────────────────────────────────────────────

class TestRenderDocxBytes:
    def test_is_valid_zip(self):
        from api.services.export_service import _render_docx_bytes
        data = _render_docx_bytes("testrepo", [_make_session()])
        assert zipfile.is_zipfile(__import__("io").BytesIO(data))

    def test_contains_document_xml(self):
        from api.services.export_service import _render_docx_bytes
        import io
        data = _render_docx_bytes("testrepo", [_make_session()])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert "word/document.xml" in zf.namelist()

    def test_contains_content_types(self):
        from api.services.export_service import _render_docx_bytes
        import io
        data = _render_docx_bytes("r", [_make_session()])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert "[Content_Types].xml" in zf.namelist()

    def test_empty_sessions(self):
        from api.services.export_service import _render_docx_bytes
        data = _render_docx_bytes("r", [])
        assert isinstance(data, bytes) and len(data) > 0


# ─── build_export_payload ───────────────────────────────────────────────────

class TestBuildExportPayload:
    # ── md ──

    def test_md_format_keys(self):
        result = _call_export("md")
        assert result["format"] == "md"
        assert result["filename"].endswith(".md")
        assert result["content_type"] == "text/markdown"
        assert "myrepo" in result["content"]

    def test_md_session_count_meta(self):
        result = _call_export("md", sessions=[_make_session(), _make_session("s-2")])
        assert result["meta"]["session_count"] == 2

    def test_md_empty_sessions(self):
        result = _call_export("md", sessions=[])
        assert result["format"] == "md"

    # ── txt ──

    def test_txt_format_keys(self):
        result = _call_export("txt")
        assert result["format"] == "txt"
        assert result["filename"].endswith(".txt")
        assert result["content_type"] == "text/plain"

    def test_txt_no_hash_chars(self):
        result = _call_export("txt")
        assert "#" not in result["content"]

    # ── json ──

    def test_json_format_keys(self):
        result = _call_export("json")
        assert result["format"] == "json"
        assert result["filename"].endswith(".json")
        assert result["content_type"] == "application/json"

    def test_json_content_parseable(self):
        result = _call_export("json")
        parsed = json.loads(result["content"])
        assert "sessions" in parsed
        assert "messages" in parsed
        assert "repo_name" in parsed

    def test_json_message_count_in_meta(self):
        result = _call_export("json", sessions=[_make_session()])
        assert result["meta"]["message_count"] == 2  # user + assistant

    def test_json_empty_sessions(self):
        result = _call_export("json", sessions=[])
        parsed = json.loads(result["content"])
        assert parsed["session_count"] == 0

    # ── pdf ──

    def test_pdf_format_keys(self):
        result = _call_export("pdf")
        assert result["format"] == "pdf"
        assert result["filename"].endswith(".pdf")
        assert result["content_type"] == "application/pdf"
        assert result["meta"]["encoding"] == "base64"

    def test_pdf_content_is_base64(self):
        result = _call_export("pdf")
        raw = base64.b64decode(result["content"])
        assert raw.startswith(b"%PDF-")

    # ── docx ──

    def test_docx_format_keys(self):
        result = _call_export("docx")
        assert result["format"] == "docx"
        assert result["filename"].endswith(".docx")
        assert "wordprocessingml" in result["content_type"]

    def test_docx_content_is_base64_zip(self):
        import io
        result = _call_export("docx")
        raw = base64.b64decode(result["content"])
        assert zipfile.is_zipfile(io.BytesIO(raw))

    # ── negative paths ──

    def test_unsupported_format_raises_value_error(self):
        from api.services.export_service import build_export_payload
        with pytest.raises(ValueError, match="Unsupported export format"):
            build_export_payload(repo_name="r", format_name="xml", sessions=[])

    def test_case_insensitive_format(self):
        result = _call_export("MD")
        assert result["format"] == "md"

    def test_filename_contains_repo_name(self):
        result = _call_export("md")
        assert "myrepo" in result["filename"]

