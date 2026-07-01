import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.wiki import database_recovery_chats
from app.wiki.database_recovery import (
    RemoteSqliteSource,
    export_knowledge_sqlite,
)
from app.wiki.database_recovery_chats import (
    export_chat_backend_sqlite,
    export_librechat_mongo,
)


class DatabaseRecoveryTests(unittest.TestCase):
    def test_exports_knowledge_facts_and_wiki_pages_as_markdown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "knowledge.db"
            con = sqlite3.connect(db_path)
            con.executescript(
                """
                create table facts (
                    id text, domain text, key text, value text, source text,
                    confidence real, created_at text, updated_at text, type text, tags text
                );
                create table facts_archive (
                    id text, domain text, key text, value text, source text,
                    confidence real, created_at text, updated_at text, type text, tags text
                );
                create table wiki_pages (
                    slug text, domain text, title text, body_md text, updated_at text
                );
                create table curation_items (
                    id text, title text, summary text, created_at text
                );
                insert into facts values (
                    'fact-1', 'career', 'employer', 'Example Co.', 'chat',
                    1.0, '2026-01-01', '2026-01-02', 'identity', '["work"]'
                );
                insert into facts_archive values (
                    'old-1', 'career', 'old-role', 'Intern', 'chat',
                    0.8, '2025-01-01', '2025-01-02', 'state', '[]'
                );
                insert into wiki_pages values (
                    'career/index', 'career', 'Career', 'Managed page body.', '2026-01-03'
                );
                insert into curation_items values (
                    'cur-1', 'Review item', 'Needs attention.', '2026-01-04'
                );
                """
            )
            con.commit()

            paths = export_knowledge_sqlite(
                db_path,
                RemoteSqliteSource("legacy", 110, "/data/knowledge.db"),
                root / "out",
            )

            names = sorted(path.relative_to(root / "out").as_posix() for path in paths)
            self.assertEqual(
                ["legacy/curation.md", "legacy/facts.md", "legacy/wiki-pages/career.md"],
                names,
            )
            self.assertIn("`employer`: Example Co.", (root / "out/legacy/facts.md").read_text())
            self.assertIn(
                "Managed page body.",
                (root / "out/legacy/wiki-pages/career.md").read_text(),
            )

    def test_exports_chat_backend_conversation_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "chat.db"
            con = sqlite3.connect(db_path)
            con.executescript(
                """
                create table conversations (
                    session_id text, created_at text, timezone text, title text,
                    saved integer, updated_at text, title_source text, llm_settings text
                );
                create table messages (
                    id integer, session_id text, role text, content text,
                    created_at text, metadata text
                );
                insert into conversations values (
                    'session-1', '2026-01-01', 'UTC', 'Garden Plan',
                    1, '2026-01-02', 'manual', '{}'
                );
                insert into messages values (
                    1, 'session-1', 'user', 'Plant tomatoes.', '2026-01-01T12:00:00Z', '{}'
                );
                """
            )
            con.commit()

            paths = export_chat_backend_sqlite(
                db_path,
                RemoteSqliteSource("chat", 111, "/data/chat.db"),
                root / "out",
            )

            self.assertEqual(2, len(paths))
            conversation = next(path for path in paths if path.name != "index.md")
            self.assertIn("Plant tomatoes.", conversation.read_text())
            self.assertIn("Garden Plan", (root / "out/chat/index.md").read_text())

    def test_exports_librechat_payload_without_user_records(self):
        payload = {
            "conversations": [
                {"conversationId": "c1", "title": "Profile", "createdAt": "2026-01-01"}
            ],
            "messages": [
                {
                    "conversationId": "c1",
                    "sender": "user",
                    "text": "I prefer concise notes.",
                    "createdAt": "2026-01-01T12:00:00Z",
                }
            ],
            "users": [{"email": "not-exported@example.com"}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(database_recovery_chats, "_librechat_payload", return_value=payload):
                paths = export_librechat_mongo(Path(temp_dir), ssh_host="unused")

            body = "\n".join(path.read_text() for path in paths)
            self.assertIn("I prefer concise notes.", body)
            self.assertNotIn("not-exported@example.com", body)


if __name__ == "__main__":
    unittest.main()
