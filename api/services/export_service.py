"""Export repository memory conversations into text-friendly formats."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Dict, Any, List
from xml.sax.saxutils import escape


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _render_markdown(repo_name: str, sessions: List[Dict[str, Any]]) -> str:
    lines: List[str] = [
        f"# Repository Memory Export - {repo_name}",
        "",
        f"Generated at: {_now_iso()}",
        "",
    ]
    for session in sessions:
        lines.append(f"## {session.get('title') or 'Untitled conversation'}")
        lines.append("")
        lines.append(f"- Session ID: `{session.get('id')}`")
        lines.append(f"- Session Type: `{session.get('session_type', 'quick_ask')}`")
        lines.append(f"- Updated: `{session.get('updated_at')}`")
        lines.append("")

        summary = session.get("summary") or {}
        if summary:
            lines.append("### Executive Summary")
            lines.append(summary.get("executive_summary") or "-")
            lines.append("")
            lines.append("### Technical Summary")
            lines.append(summary.get("technical_summary") or "-")
            lines.append("")

        lines.append("### Conversation History")
        session_messages = session.get("messages") or []
        if not session_messages:
            lines.append("_No persisted messages found for this session._")
            lines.append("")

        for message in session_messages:
            role = (message.get("role") or "assistant").upper()
            created_at = message.get("created_at") or "unknown"
            lines.append(f"- **{role}** ({created_at})")
            if message.get("query_mode"):
                lines.append(f"  - mode: `{message.get('query_mode')}`")
            if message.get("latency_ms") is not None:
                lines.append(f"  - latency: `{message.get('latency_ms')} ms`")
            retrieved_files = message.get("retrieved_files") or []
            if retrieved_files:
                lines.append(f"  - retrieved_files: `{len(retrieved_files)}`")
            lines.append("")
            lines.append(message.get("content") or "")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def _render_plain_text(repo_name: str, sessions: List[Dict[str, Any]]) -> str:
    md = _render_markdown(repo_name, sessions)
    return md.replace("#", "").replace("`", "")


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_pdf_bytes(repo_name: str, sessions: List[Dict[str, Any]]) -> bytes:
    plain = _render_plain_text(repo_name, sessions)
    lines = [line.strip() for line in plain.splitlines() if line.strip()]
    lines = lines[:120]

    content_lines = [
        "BT",
        "/F1 10 Tf",
        "48 780 Td",
        "14 TL",
    ]
    for line in lines:
        content_lines.append(f"({_pdf_escape(line[:140])}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"5 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream\nendobj\n",
    ]

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = b""
    offsets = [0]
    current_offset = len(header)
    for obj in objects:
        offsets.append(current_offset)
        body += obj
        current_offset += len(obj)

    xref_offset = len(header) + len(body)
    xref = [f"xref\n0 {len(objects) + 1}\n".encode("latin-1"), b"0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref.append(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("latin-1")

    return header + body + b"".join(xref) + trailer


def _render_docx_bytes(repo_name: str, sessions: List[Dict[str, Any]]) -> bytes:
    plain = _render_plain_text(repo_name, sessions)
    lines = [line.strip() for line in plain.splitlines() if line.strip()]
    lines = lines[:300]

    paragraphs = []
    for line in lines:
        safe = escape(line)
        paragraphs.append(f"<w:p><w:r><w:t xml:space=\"preserve\">{safe}</w:t></w:r></w:p>")

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:wpc=\"http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas\" "
        "xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" "
        "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" "
        "xmlns:v=\"urn:schemas-microsoft-com:vml\" "
        "xmlns:wp14=\"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing\" "
        "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" "
        "xmlns:w10=\"urn:schemas-microsoft-com:office:word\" "
        "xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" "
        "xmlns:w15=\"http://schemas.microsoft.com/office/word/2012/wordml\" "
        "xmlns:wpg=\"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup\" "
        "xmlns:wpi=\"http://schemas.microsoft.com/office/word/2010/wordprocessingInk\" "
        "xmlns:wne=\"http://schemas.microsoft.com/office/2006/wordml\" "
        "xmlns:wps=\"http://schemas.microsoft.com/office/word/2010/wordprocessingShape\" "
        "mc:Ignorable=\"w14 w15 wp14\">"
        "<w:body>"
        f"<w:p><w:r><w:t>Repository Memory Export - {escape(repo_name)}</w:t></w:r></w:p>"
        + "".join(paragraphs)
        + "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\"/></w:sectPr>"
        "</w:body></w:document>"
    )

    content_types = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "</Types>"
    )

    rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "</Relationships>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def build_export_payload(
    *,
    repo_name: str,
    format_name: str,
    sessions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    format_name = format_name.lower()
    base_filename = f"repository-memory-{repo_name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    if format_name == "md":
        content = _render_markdown(repo_name, sessions)
        return {
            "filename": f"{base_filename}.md",
            "format": "md",
            "content_type": "text/markdown",
            "content": content,
            "meta": {"session_count": len(sessions)},
        }

    if format_name == "txt":
        content = _render_plain_text(repo_name, sessions)
        return {
            "filename": f"{base_filename}.txt",
            "format": "txt",
            "content_type": "text/plain",
            "content": content,
            "meta": {"session_count": len(sessions)},
        }

    if format_name == "json":
        all_messages = []
        for session in sessions:
            for message in session.get("messages") or []:
                all_messages.append({
                    "chat_id": session.get("id"),
                    "chat_title": session.get("title"),
                    **message,
                })
        return {
            "filename": f"{base_filename}.json",
            "format": "json",
            "content_type": "application/json",
            "content": json.dumps(
                {
                    "generated_at": _now_iso(),
                    "repo_name": repo_name,
                    "session_count": len(sessions),
                    "message_count": len(all_messages),
                    "sessions": sessions,
                    "messages": all_messages,
                },
                indent=2,
            ),
            "meta": {"session_count": len(sessions), "message_count": len(all_messages)},
        }

    # Keep these formats available to the frontend contract even without heavy binary libs.
    if format_name in {"pdf", "docx"}:
        if format_name == "pdf":
            data = _render_pdf_bytes(repo_name, sessions)
            content_type = "application/pdf"
        else:
            data = _render_docx_bytes(repo_name, sessions)
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        return {
            "filename": f"{base_filename}.{format_name}",
            "format": format_name,
            "content_type": content_type,
            "content": base64.b64encode(data).decode("ascii"),
            "meta": {
                "session_count": len(sessions),
                "encoding": "base64",
            },
        }

    raise ValueError(f"Unsupported export format: {format_name}")

