import json
import tempfile
import unittest
from pathlib import Path

from app.wiki.anthropic_extraction import ANTHROPIC_MESSAGES_URL
from app.wiki.extraction_packets import ExtractionPacketError
from app.wiki.google_extraction import GOOGLE_GENERATE_CONTENT_BASE_URL
from app.wiki.model_profiles import (
    ANTHROPIC_SONNET46_EXTRACTION,
    GOOGLE_GEMINI35_FLASH_EXTRACTION,
    OPENAI_GPT55_EXTRACTION,
)
from app.wiki.openai_extraction import OPENAI_RESPONSES_URL
from app.wiki.source_extraction import (
    SourceExtractionJob,
    extract_source_to_workspace,
)
from tests.helpers import (
    JsonResponse,
    RawResponse,
    extraction_packet,
    fact_record,
    source_record,
    wiki_workspace,
    write_text_source,
)


def _anthropic_response(source_id: str):
    return {
        "content": [
            {
                "type": "tool_use",
                "name": "emit_memex_extraction",
                "input": extraction_packet(source_id),
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def _openai_response(source_id: str):
    return {
        "output_text": json.dumps(extraction_packet(source_id)),
        "usage": {"input_tokens": 12, "output_tokens": 24},
    }


def _google_response(source_id: str):
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                extraction_packet(
                                    source_id,
                                    title="Profile PDF",
                                    source_type="pdf",
                                    locator="page 1",
                                )
                            )
                        }
                    ]
                }
            }
        ],
        "usageMetadata": {"promptTokenCount": 13, "candidatesTokenCount": 26},
    }


class WikiSourceExtractionWorkflowTests(unittest.TestCase):
    def test_extract_source_to_workspace_uses_default_sonnet_and_saves_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = write_text_source(root, "profile.txt")
            workspace = wiki_workspace(root)
            seen = {}

            def opener(request, timeout):
                seen["url"] = request.full_url
                seen["body"] = json.loads(request.data.decode("utf-8"))
                return JsonResponse(_anthropic_response("source-llm"))

            result = extract_source_to_workspace(
                workspace,
                SourceExtractionJob("source-llm", source_path, title="Profile"),
                {"ANTHROPIC_API_KEY": "secret"},
                opener=opener,
            )

            self.assertEqual(ANTHROPIC_MESSAGES_URL, seen["url"])
            self.assertEqual(ANTHROPIC_SONNET46_EXTRACTION.model, seen["body"]["model"])
            self.assertEqual(ANTHROPIC_SONNET46_EXTRACTION.profile_id, result.model_spec)
            self.assertEqual({"input_tokens": 10, "output_tokens": 20}, result.usage)
            self.assertEqual("source-llm", workspace.data_store.load_source("source-llm").source_id)
            manifest = workspace.source_assets().load_manifest("source-llm")
            stored_original = (
                workspace.source_assets().asset_dir("source-llm") / manifest.stored_path
            )
            self.assertEqual("local_path", manifest.source_kind)
            self.assertEqual("profile.txt", manifest.original_name)
            self.assertEqual("text/plain", manifest.mime_type)
            self.assertEqual("anthropic", manifest.extraction_provider)
            self.assertEqual(ANTHROPIC_SONNET46_EXTRACTION.model, manifest.extraction_model)
            self.assertEqual({"input_tokens": 10, "output_tokens": 20}, manifest.usage)
            self.assertEqual(
                "Alice joined Example Co.", stored_original.read_text(encoding="utf-8")
            )
            self.assertTrue(result.created)
            self.assertFalse(result.duplicate)

    def test_extract_source_to_workspace_can_use_openai_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = write_text_source(root, "profile.txt")
            workspace = wiki_workspace(root)
            seen = {}

            def opener(request, timeout):
                seen["url"] = request.full_url
                seen["body"] = json.loads(request.data.decode("utf-8"))
                return JsonResponse(_openai_response("source-openai"))

            result = extract_source_to_workspace(
                workspace,
                SourceExtractionJob(
                    "source-openai",
                    source_path,
                    title="Profile",
                    model_spec=OPENAI_GPT55_EXTRACTION.profile_id,
                ),
                {"OPENAI_API_KEY": "secret"},
                opener=opener,
            )

            self.assertEqual(OPENAI_RESPONSES_URL, seen["url"])
            self.assertEqual(OPENAI_GPT55_EXTRACTION.model, seen["body"]["model"])
            self.assertEqual(OPENAI_GPT55_EXTRACTION.profile_id, result.model_spec)
            self.assertEqual({"input_tokens": 12, "output_tokens": 24}, result.usage)
            self.assertEqual("source-openai", result.source.source_id)
            manifest = workspace.source_assets().load_manifest("source-openai")
            self.assertEqual("openai", manifest.extraction_provider)
            self.assertEqual(OPENAI_GPT55_EXTRACTION.model, manifest.extraction_model)
            self.assertTrue(result.created)
            self.assertFalse(result.duplicate)

    def test_extract_source_to_workspace_records_typed_text_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = write_text_source(root, "meeting-note.txt", "Typed source fact.")
            workspace = wiki_workspace(root)

            def opener(request, timeout):
                return JsonResponse(_anthropic_response("typed-note"))

            result = extract_source_to_workspace(
                workspace,
                SourceExtractionJob(
                    "typed-note",
                    source_path,
                    title="Meeting Note",
                    source_type="text",
                    source_kind="typed_text",
                    mime_type="text/plain",
                ),
                {"ANTHROPIC_API_KEY": "secret"},
                opener=opener,
            )

            manifest = workspace.source_assets().load_manifest("typed-note")
            stored_original = (
                workspace.source_assets().asset_dir("typed-note") / manifest.stored_path
            )
            self.assertEqual("typed_text", manifest.source_kind)
            self.assertEqual("meeting-note.txt", manifest.original_name)
            self.assertEqual("text/plain", manifest.mime_type)
            self.assertEqual("Typed source fact.", stored_original.read_text(encoding="utf-8"))
            self.assertEqual("typed-note", result.source.source_id)

    def test_extract_source_to_workspace_can_use_google_profile_for_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "profile.pdf"
            source_path.write_bytes(b"%PDF-1.7\n")
            workspace = wiki_workspace(root)
            seen = {}

            def opener(request, timeout):
                seen["url"] = request.full_url
                seen["body"] = json.loads(request.data.decode("utf-8"))
                return JsonResponse(_google_response("source-google-pdf"))

            result = extract_source_to_workspace(
                workspace,
                SourceExtractionJob(
                    "source-google-pdf",
                    source_path,
                    title="Profile PDF",
                    model_spec=GOOGLE_GEMINI35_FLASH_EXTRACTION.profile_id,
                ),
                {"GEMINI_API_KEY": "secret"},
                opener=opener,
            )

            self.assertEqual(
                (f"{GOOGLE_GENERATE_CONTENT_BASE_URL}/gemini-3.5-flash:generateContent"),
                seen["url"],
            )
            parts = seen["body"]["contents"][0]["parts"]
            self.assertEqual("application/pdf", parts[1]["inline_data"]["mime_type"])
            self.assertEqual("source-google-pdf", result.source.source_id)
            self.assertEqual(
                {"promptTokenCount": 13, "candidatesTokenCount": 26},
                result.usage,
            )
            manifest = workspace.source_assets().load_manifest("source-google-pdf")
            self.assertEqual("google", manifest.extraction_provider)
            self.assertEqual(
                GOOGLE_GEMINI35_FLASH_EXTRACTION.model,
                manifest.extraction_model,
            )

    def test_extract_source_to_workspace_rejects_unsupported_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = write_text_source(root, "profile.txt")
            workspace = wiki_workspace(root)

            with self.assertRaises(ExtractionPacketError):
                extract_source_to_workspace(
                    workspace,
                    SourceExtractionJob(
                        "source-llm",
                        source_path,
                        model_spec="mistral:large",
                    ),
                    {"ANTHROPIC_API_KEY": "secret"},
                )
            self.assertFalse(workspace.source_assets().asset_dir("source-llm").exists())

    def test_extract_source_to_workspace_cleans_staging_after_provider_json_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = write_text_source(root, "profile.txt")
            workspace = wiki_workspace(root)

            def opener(request, timeout):
                return RawResponse(b"not-json")

            with self.assertRaisesRegex(ExtractionPacketError, "OpenAI response was not JSON"):
                extract_source_to_workspace(
                    workspace,
                    SourceExtractionJob(
                        "source-json-failure",
                        source_path,
                        model_spec=OPENAI_GPT55_EXTRACTION.profile_id,
                    ),
                    {"OPENAI_API_KEY": "secret"},
                    opener=opener,
                )

            asset_store = workspace.source_assets()
            self.assertFalse(asset_store.asset_dir("source-json-failure").exists())
            if asset_store.staging_root.exists():
                self.assertEqual([], list(asset_store.staging_root.iterdir()))
            with self.assertRaises(FileNotFoundError):
                workspace.data_store.load_source("source-json-failure")

    def test_extract_source_to_workspace_returns_existing_source_for_duplicate_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_path = write_text_source(root, "profile.txt")
            duplicate_path = write_text_source(root, "copy.txt")
            workspace = wiki_workspace(root)
            existing = source_record(
                "source-existing",
                fact_record("fact-joined", "Alice joined Example Co."),
            )
            workspace.save_source(existing)
            manifest = (
                workspace.source_assets()
                .stage_file(
                    "source-existing",
                    first_path,
                    source_kind="local_path",
                )
                .commit(
                    extraction_provider="anthropic",
                    extraction_model=ANTHROPIC_SONNET46_EXTRACTION.model,
                    extracted_at="2026-06-23T00:00:00Z",
                )
            )

            def opener(request, timeout):
                self.fail("duplicate source should not call the provider")

            result = extract_source_to_workspace(
                workspace,
                SourceExtractionJob("source-copy", duplicate_path, title="Copy"),
                {"ANTHROPIC_API_KEY": "secret"},
                opener=opener,
            )

            self.assertFalse(result.created)
            self.assertTrue(result.duplicate)
            self.assertEqual("source-existing", result.duplicate_source_id)
            self.assertEqual(existing, result.source)
            self.assertEqual(manifest.sha256, result.sha256)
            self.assertFalse(workspace.source_assets().asset_dir("source-copy").exists())
            with self.assertRaises(FileNotFoundError):
                workspace.data_store.load_source("source-copy")

    def test_extract_source_to_workspace_can_allow_duplicate_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_path = write_text_source(root, "profile.txt")
            duplicate_path = write_text_source(root, "copy.txt")
            workspace = wiki_workspace(root)
            workspace.save_source(
                source_record(
                    "source-existing",
                    fact_record("fact-joined", "Alice joined Example Co."),
                )
            )
            existing_manifest = (
                workspace.source_assets()
                .stage_file(
                    "source-existing",
                    first_path,
                    source_kind="local_path",
                )
                .commit(
                    extraction_provider="anthropic",
                    extraction_model=ANTHROPIC_SONNET46_EXTRACTION.model,
                    extracted_at="2026-06-23T00:00:00Z",
                )
            )

            def opener(request, timeout):
                return JsonResponse(_anthropic_response("source-copy"))

            result = extract_source_to_workspace(
                workspace,
                SourceExtractionJob(
                    "source-copy",
                    duplicate_path,
                    title="Copy",
                    allow_duplicate=True,
                ),
                {"ANTHROPIC_API_KEY": "secret"},
                opener=opener,
            )

            copy_manifest = workspace.source_assets().load_manifest("source-copy")
            self.assertTrue(result.created)
            self.assertFalse(result.duplicate)
            self.assertEqual("source-copy", result.source.source_id)
            self.assertEqual(existing_manifest.sha256, result.sha256)
            self.assertEqual(existing_manifest.sha256, copy_manifest.sha256)
            self.assertEqual(
                "source-copy", workspace.data_store.load_source("source-copy").source_id
            )

    def test_extract_source_to_workspace_rejects_source_id_collision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = write_text_source(root, "profile.txt")
            workspace = wiki_workspace(root)
            workspace.save_source(
                source_record(
                    "source-existing",
                    fact_record("fact-joined", "Alice joined Example Co."),
                )
            )

            with self.assertRaisesRegex(ValueError, "already exists"):
                extract_source_to_workspace(
                    workspace,
                    SourceExtractionJob(
                        "source-existing",
                        source_path,
                        title="Collision",
                        allow_duplicate=True,
                    ),
                    {"ANTHROPIC_API_KEY": "secret"},
                )

            self.assertEqual("Profile", workspace.data_store.load_source("source-existing").title)


if __name__ == "__main__":
    unittest.main()
