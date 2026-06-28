import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.wiki.extraction import (
    extract_source_from_path,
    extract_source_from_text,
    extract_text_facts,
)
from app.wiki.records import SourceRecord
from tests.helpers import wiki_workspace, write_text_source

TEXT = """# Profile

Alice joined Example Co.
She led platform work.

- Alice presented at PyCon.
- Alice lives in Boston.

```
This code block is not a fact.
```
"""


class WikiExtractionTests(unittest.TestCase):
    def test_extract_text_facts_splits_paragraphs_and_bullets(self):
        facts = extract_text_facts(TEXT)

        self.assertEqual(
            (
                "Alice joined Example Co. She led platform work.",
                "Alice presented at PyCon.",
                "Alice lives in Boston.",
            ),
            tuple(fact.text for fact in facts),
        )
        self.assertEqual((3, 4), (facts[0].line_start, facts[0].line_end))

    def test_extract_source_from_text_creates_stable_source_record(self):
        source = extract_source_from_text(
            "source-1",
            TEXT,
            source_type="markdown",
            origin="notes/profile.md",
        )
        moved = extract_source_from_text(
            "source-1",
            "\n\n" + TEXT,
            source_type="markdown",
            origin="notes/profile.md",
        )

        self.assertEqual("Profile", source.title)
        self.assertEqual("markdown", source.source_type)
        self.assertEqual(
            "Alice joined Example Co. She led platform work.",
            source.summary,
        )
        self.assertEqual(3, len(source.facts))
        self.assertEqual(
            tuple(fact.fact_id for fact in source.facts),
            tuple(fact.fact_id for fact in moved.facts),
        )
        self.assertEqual(
            tuple(fact.signature() for fact in source.facts),
            tuple(fact.signature() for fact in moved.facts),
        )
        self.assertEqual("notes/profile.md", source.facts[0].provenance["origin"])

    def test_extract_source_from_text_records_empty_and_duplicate_issues(self):
        empty = extract_source_from_text("empty", "# Empty\n\n")
        duplicates = extract_source_from_text(
            "dupes",
            "- Alice joined Example Co.\n- Alice joined Example Co.\n",
        )

        self.assertEqual((), empty.facts)
        self.assertEqual(("No fact-like text extracted.",), empty.extraction_issues)
        self.assertEqual(1, len(duplicates.facts))
        self.assertEqual(
            ("Skipped 1 duplicate fact candidate(s).",),
            duplicates.extraction_issues,
        )

    def test_extract_source_from_path_and_workspace_import_text_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            note_path = write_text_source(root, "profile.md", TEXT)
            source = extract_source_from_path(note_path, "source-1")
            workspace = wiki_workspace(root)

            imported = workspace.import_text_source(note_path, "source-1").source

            self.assertEqual(source, imported)
            self.assertEqual(source, workspace.data_store.load_source("source-1"))

    def test_cli_extract_text_imports_source_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            note_path = write_text_source(root, "profile.md", TEXT)
            script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_dev.py"
            command = [
                sys.executable,
                str(script),
                "--repo-root",
                str(root),
                "extract-text",
                "source-1",
                str(note_path),
                "--title",
                "Profile Title",
            ]

            result = subprocess.run(command, check=True, text=True, capture_output=True)
            stored_path = root / "data" / "sources" / "source-1.json"
            stored = SourceRecord.from_dict(json.loads(stored_path.read_text(encoding="utf-8")))

            self.assertIn("extracted source source-1 (3 facts)", result.stdout)
            self.assertEqual("Profile Title", stored.title)
            self.assertEqual("markdown", stored.source_type)

            duplicate_command = command.copy()
            duplicate_command[5] = "source-2"
            duplicate = subprocess.run(
                duplicate_command,
                check=True,
                text=True,
                capture_output=True,
            )

            self.assertIn(
                "duplicate source source-2; showing existing source-1",
                duplicate.stdout,
            )
            self.assertFalse((root / "data" / "sources" / "source-2.json").exists())


if __name__ == "__main__":
    unittest.main()
