"""Conversation database exporters for recovered source drafts."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .database_recovery import (
    RemoteSqliteSource,
    _connect,
    _format_millis,
    _group_by,
    _json_obj,
    _message_block,
    _metadata,
    _plain_json,
    _rows,
    _slug,
    _source_note,
    _title,
    _write,
)


def export_chat_backend_sqlite(
    db_path: Path,
    source: RemoteSqliteSource,
    out_dir: Path,
) -> list[Path]:
    con = _connect(db_path)
    conversations = _rows(con, "select * from conversations order by created_at, session_id")
    messages = _group_by(
        _rows(con, "select * from messages order by session_id, id"),
        "session_id",
    )
    base = out_dir / source.label / "conversations"
    index = [_title("Recovered Chat Backend Conversations"), _source_note(source)]
    paths: list[Path] = []
    for convo in conversations:
        title = str(convo.get("title") or "Untitled conversation")
        session_id = str(convo["session_id"])
        index.append(f"- `{session_id}`: {title} ({len(messages.get(session_id, ()))} messages)")
        body = [
            _title(f"Chat Backend Conversation: {title}"),
            _metadata(convo, skip={"llm_settings"}),
        ]
        for msg in messages.get(session_id, ()):
            body.append(_message_block(msg.get("role"), msg.get("created_at"), msg.get("content")))
        paths.append(_write(base / f"conversation-{_slug(session_id)[:16]}.md", "\n".join(body)))
    paths.append(_write(out_dir / source.label / "index.md", "\n".join(index)))
    return paths


def export_opencode_sqlite(
    db_path: Path,
    source: RemoteSqliteSource,
    out_dir: Path,
) -> list[Path]:
    con = _connect(db_path)
    sessions = _rows(con, "select * from session order by time_created, id")
    messages = _group_by(_rows(con, "select * from message order by time_created, id"), "session_id")
    parts = _group_by(_rows(con, "select * from part order by time_created, id"), "message_id")
    base = out_dir / source.label / "sessions"
    index = [_title("Recovered Opencode Sessions"), _source_note(source)]
    paths: list[Path] = []
    for session in sessions:
        title = str(session.get("title") or session.get("slug") or "Untitled session")
        sid = str(session["id"])
        index.append(f"- `{sid}`: {title} ({len(messages.get(sid, ()))} messages)")
        body = [_title(f"Opencode Session: {title}"), _metadata(session)]
        for msg in messages.get(sid, ()):
            message_data = _json_obj(msg.get("data"))
            role = message_data.get("role") or "message"
            body.append(f"## {role} at {_format_millis(msg.get('time_created'))}\n")
            summary = message_data.get("summary")
            if summary:
                body.append(f"Summary: {_plain_json(summary)}\n")
            for part in parts.get(str(msg["id"]), ()):
                body.append(_opencode_part_text(part))
        paths.append(_write(base / f"session-{_slug(sid)[:16]}.md", "\n".join(body)))
    paths.append(_write(out_dir / source.label / "index.md", "\n".join(index)))
    return paths


def export_librechat_mongo(out_dir: Path, *, ssh_host: str = "proxmox-tunnel") -> list[Path]:
    payload = _librechat_payload(ssh_host)
    conversations = payload.get("conversations", [])
    messages = _group_by(payload.get("messages", []), "conversationId")
    base = out_dir / "librechat-115" / "conversations"
    index = [_title("Recovered LibreChat Conversations"), "Source: LXC 115 MongoDB `LibreChat`.\n"]
    paths: list[Path] = []
    for convo in sorted(conversations, key=lambda row: str(row.get("createdAt", ""))):
        title = str(convo.get("title") or "Untitled conversation")
        cid = str(convo.get("conversationId") or convo.get("_id"))
        convo_messages = sorted(messages.get(cid, ()), key=lambda row: str(row.get("createdAt", "")))
        index.append(f"- `{cid}`: {title} ({len(convo_messages)} messages)")
        body = [_title(f"LibreChat Conversation: {title}"), _metadata(convo)]
        for msg in convo_messages:
            body.append(_message_block(msg.get("sender"), msg.get("createdAt"), msg.get("text")))
        paths.append(_write(base / f"conversation-{_slug(cid)[:16]}.md", "\n".join(body)))
    paths.append(_write(out_dir / "librechat-115" / "index.md", "\n".join(index)))
    return paths


def _librechat_payload(ssh_host: str) -> Mapping[str, Any]:
    script = """
const conversations = db.conversations.find({}, {projection: {
  _id: 1, conversationId: 1, title: 1, createdAt: 1, updatedAt: 1,
  endpoint: 1, endpointType: 1, model: 1, tags: 1
}}).toArray();
const messages = db.messages.find({}, {projection: {
  _id: 1, conversationId: 1, messageId: 1, parentMessageId: 1, sender: 1,
  text: 1, createdAt: 1, updatedAt: 1, endpoint: 1, model: 1, isCreatedByUser: 1,
  error: 1
}}).toArray();
print(JSON.stringify({conversations, messages}));
"""
    command = (
        "pct exec 115 -- docker exec chat-mongodb "
        f"mongosh LibreChat --quiet --eval {shlex.quote(script)}"
    )
    result = subprocess.run(
        ["ssh", ssh_host, command],
        check=True,
        capture_output=True,
    )
    return json.loads(result.stdout.decode("utf-8").strip())


def _opencode_part_text(row: Mapping[str, Any]) -> str:
    data = _json_obj(row.get("data"))
    part_type = data.get("type") or "part"
    text = data.get("text") or data.get("content") or data.get("snapshot")
    if isinstance(text, str) and text.strip():
        return f"### {part_type}\n\n{text.strip()}\n"
    return f"### {part_type}\n\n```json\n{_plain_json(data)}\n```\n"
