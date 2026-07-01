"""Recover old app databases into markdown source drafts."""

from __future__ import annotations

import json
import re
import shlex
import sqlite3
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class RemoteSqliteSource:
    label: str
    container_id: int | None
    path: str


KNOWLEDGE_SOURCES = (
    RemoteSqliteSource(
        "knowledge-live-110",
        110,
        "/opt/mcp-servers/data/knowledge.db",
    ),
    RemoteSqliteSource(
        "knowledge-final-archive-118",
        118,
        "/srv/knowledge-sources/archive/legacy-knowledge/final-db-archive/"
        "knowledge-final-20260527T160206Z.sqlite",
    ),
)

SMALL_SOURCES = (
    RemoteSqliteSource("knowledge-memory-110", 110, "/opt/mcp-servers/data/memory.db"),
    RemoteSqliteSource("knowledge-rag-index-110", 110, "/opt/mcp-servers/data/rag_index.db"),
)

CHAT_BACKEND = RemoteSqliteSource(
    "chat-backend-111",
    111,
    "/opt/chat-backend/data/chat_sessions.db",
)

OPENCODE = RemoteSqliteSource(
    "opencode-114",
    114,
    "/root/.local/share/opencode/opencode.db",
)

LOCAL_OPENCODE = RemoteSqliteSource(
    "opencode-local-laptop",
    None,
    "/home/jack/.local/share/opencode/opencode.db",
)


def run_recovery(
    out_dir: str | Path,
    *,
    ssh_host: str = "proxmox-tunnel",
    include_librechat: bool = True,
) -> list[Path]:
    from .database_recovery_chats import (
        export_chat_backend_sqlite,
        export_librechat_mongo,
        export_opencode_sqlite,
    )

    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="memex-db-recovery-") as temp_dir:
        temp = Path(temp_dir)
        for source in KNOWLEDGE_SOURCES:
            written.extend(export_knowledge_sqlite(_remote_sqlite(source, ssh_host, temp), source, output))
        for source in SMALL_SOURCES:
            written.extend(export_generic_sqlite(_remote_sqlite(source, ssh_host, temp), source, output))
        written.extend(export_chat_backend_sqlite(_remote_sqlite(CHAT_BACKEND, ssh_host, temp), CHAT_BACKEND, output))
        written.extend(export_opencode_sqlite(_remote_sqlite(OPENCODE, ssh_host, temp), OPENCODE, output))
        local_opencode_path = Path(LOCAL_OPENCODE.path)
        if local_opencode_path.exists():
            written.extend(export_opencode_sqlite(local_opencode_path, LOCAL_OPENCODE, output))
    if include_librechat:
        written.extend(export_librechat_mongo(output, ssh_host=ssh_host))
    written.append(write_inventory(output, written))
    return written


def export_knowledge_sqlite(
    db_path: Path,
    source: RemoteSqliteSource,
    out_dir: Path,
) -> list[Path]:
    con = _connect(db_path)
    base = out_dir / source.label
    paths = [
        _write(base / "facts.md", _knowledge_facts_markdown(con, source)),
        _write(base / "curation.md", _knowledge_curation_markdown(con, source)),
    ]
    for domain, pages in _group_by(_rows(con, "select * from wiki_pages order by domain, slug"), "domain").items():
        paths.append(
            _write(
                base / "wiki-pages" / f"{_slug(domain)}.md",
                _wiki_pages_markdown(source, domain, pages),
            )
        )
    return paths


def export_generic_sqlite(
    db_path: Path,
    source: RemoteSqliteSource,
    out_dir: Path,
) -> list[Path]:
    con = _connect(db_path)
    lines = [_title(f"Recovered Database: {source.label}"), _source_note(source)]
    for table in _table_names(con):
        rows = _rows(con, f"select * from {table} order by 1")
        lines.append(f"## Table: {table}\n")
        lines.append(f"Rows: {len(rows)}\n")
        for row in rows:
            lines.append(_row_block(row))
    return [_write(out_dir / source.label / "tables.md", "\n".join(lines))]


def write_inventory(out_dir: Path, written: Iterable[Path]) -> Path:
    lines = [_title("Recovered Database Draft Inventory")]
    lines.append("These markdown drafts were generated from old application databases for MEMEX ingest.\n")
    draft_paths = sorted(path for path in written if path.name != "inventory.md")
    counts: dict[str, int] = defaultdict(int)
    for path in draft_paths:
        rel_parts = path.relative_to(out_dir).parts
        if rel_parts:
            counts[rel_parts[0]] += 1
    lines.append("## Counts\n")
    for label, count in sorted(counts.items()):
        lines.append(f"- `{label}`: {count} files")
    lines.append("\n## Files\n")
    for path in draft_paths:
        lines.append(f"- `{path.relative_to(out_dir)}`")
    return _write(out_dir / "inventory.md", "\n".join(lines))


def _remote_sqlite(source: RemoteSqliteSource, ssh_host: str, temp_dir: Path) -> Path:
    target = temp_dir / f"{source.label}.sqlite"
    remote_command = f"pct exec {source.container_id} -- cat {shlex.quote(source.path)}"
    result = subprocess.run(
        ["ssh", ssh_host, remote_command],
        check=True,
        capture_output=True,
    )
    target.write_bytes(result.stdout)
    return target


def _knowledge_facts_markdown(con: sqlite3.Connection, source: RemoteSqliteSource) -> str:
    lines = [_title(f"Recovered Knowledge Facts: {source.label}"), _source_note(source)]
    for table in ("facts", "facts_archive"):
        if not _table_exists(con, table):
            continue
        lines.append(f"## {table}\n")
        for domain, facts in _group_by(_rows(con, f"select * from {table} order by domain, key"), "domain").items():
            lines.append(f"### {domain}\n")
            for fact in facts:
                lines.append(f"- `{fact.get('key')}`: {fact.get('value')}")
                detail = _metadata(
                    fact,
                    skip={"id", "domain", "key", "value", "created_at", "updated_at"},
                    bullet_prefix="  - ",
                )
                if detail:
                    lines.append(detail)
    return "\n".join(lines)


def _knowledge_curation_markdown(con: sqlite3.Connection, source: RemoteSqliteSource) -> str:
    if not _table_exists(con, "curation_items"):
        return _title(f"Recovered Knowledge Curation: {source.label}")
    lines = [_title(f"Recovered Knowledge Curation: {source.label}"), _source_note(source)]
    for item in _rows(con, "select * from curation_items order by created_at, id"):
        lines.append(f"## {item.get('title') or item.get('id')}\n")
        lines.append(_metadata(item))
        if item.get("summary"):
            lines.append(str(item["summary"]))
    return "\n".join(lines)


def _wiki_pages_markdown(source: RemoteSqliteSource, domain: str, pages: list[Mapping[str, Any]]) -> str:
    lines = [_title(f"Recovered Knowledge Wiki Pages: {domain}"), _source_note(source)]
    for page in pages:
        lines.append(f"## {page.get('title') or page.get('slug')}\n")
        lines.append(_metadata(page, skip={"body_md", "frontmatter_json"}))
        if page.get("body_md"):
            lines.append(str(page["body_md"]).strip())
    return "\n".join(lines)


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _table_names(con: sqlite3.Connection) -> list[str]:
    return [row[0] for row in con.execute("select name from sqlite_master where type='table' order by name")]


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    return bool(con.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone())


def _rows(con: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    return [dict(row) for row in con.execute(query)]


def _group_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return dict(grouped)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def _title(text: str) -> str:
    return f"# {text}\n"


def _source_note(source: RemoteSqliteSource) -> str:
    if source.container_id is None:
        return f"Source: local `{source.path}`.\n"
    return f"Source: LXC {source.container_id} `{source.path}`.\n"


def _metadata(row: Mapping[str, Any], *, skip: set[str] | None = None, bullet_prefix: str = "- ") -> str:
    omitted = skip or set()
    lines = []
    for key, value in row.items():
        if key in omitted or value in (None, "", [], {}):
            continue
        lines.append(f"{bullet_prefix}{key}: {_display(value)}")
    return "\n".join(lines) + ("\n" if lines else "")


def _row_block(row: Mapping[str, Any]) -> str:
    return "\n".join(f"- {key}: {_display(value)}" for key, value in row.items() if value not in (None, "")) + "\n"


def _message_block(role: Any, created_at: Any, content: Any) -> str:
    text = str(content or "").strip()
    if not text:
        text = "[empty message]"
    return f"## {role or 'message'} at {created_at or 'unknown time'}\n\n{text}\n"


def _json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {"text": value}
    return decoded if isinstance(decoded, dict) else {"value": decoded}


def _display(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("[", "{")):
            try:
                return _plain_json(json.loads(text))
            except json.JSONDecodeError:
                return text
        return text
    return _plain_json(value) if isinstance(value, (dict, list, tuple)) else str(value)


def _plain_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _slug(text: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return (slug or "untitled")[:90]


def _format_millis(value: Any) -> str:
    return str(value or "unknown time")
