import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.wiki.anthropic_extraction import (
    ANTHROPIC_EXTRACTION_TOOL_NAME,
    ANTHROPIC_MESSAGES_URL,
    AnthropicSourceExtractor,
)
from app.wiki.extraction_inputs import extraction_input_from_path
from app.wiki.model_profiles import ANTHROPIC_SONNET46_EXTRACTION
from tests.helpers import JsonResponse, extraction_packet, write_text_source


def _anthropic_response():
    return {
        "content": [
            {
                "type": "tool_use",
                "name": ANTHROPIC_EXTRACTION_TOOL_NAME,
                "input": extraction_packet("source-1"),
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


class WikiAnthropicExtractionTests(unittest.TestCase):
    def test_anthropic_extractor_uses_forced_tool_schema_and_normalizes_source(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            seen["api_key"] = request.get_header("X-api-key")
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return JsonResponse(_anthropic_response())

        extractor = AnthropicSourceExtractor(api_key="secret-key", opener=opener)
        result = extractor.extract(
            extraction_input_from_path(
                self._text_file("Alice joined Example Co."),
                "source-1",
                title="Profile",
            )
        )

        self.assertEqual(ANTHROPIC_MESSAGES_URL, seen["url"])
        self.assertEqual(120, seen["timeout"])
        self.assertEqual("secret-key", seen["api_key"])
        self.assertEqual(ANTHROPIC_SONNET46_EXTRACTION.model, seen["body"]["model"])
        self.assertEqual(0, seen["body"]["temperature"])
        self.assertEqual(
            {"type": "tool", "name": ANTHROPIC_EXTRACTION_TOOL_NAME},
            seen["body"]["tool_choice"],
        )
        schema = seen["body"]["tools"][0]["input_schema"]
        self.assertNotIn("run", schema["required"])
        self.assertNotIn("$schema", schema)
        self.assertEqual("source-1", result.source.source_id)
        self.assertEqual("Profile", result.source.title)
        self.assertEqual("fact_joined", result.source.facts[0].fact_id)
        self.assertEqual("anthropic", result.packet["run"]["provider"])

    def test_path_loader_supports_pdf_and_image_attachments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pdf = root / "scan.pdf"
            png = root / "scan.png"
            pdf.write_bytes(b"%PDF-1.7")
            png.write_bytes(b"png-data")

            pdf_input = extraction_input_from_path(pdf, "pdf-source")
            png_input = extraction_input_from_path(png, "png-source")

            self.assertEqual("application/pdf", pdf_input.attachments[0].mime_type)
            self.assertEqual("image/png", png_input.attachments[0].mime_type)

    def test_extract_script_help_loads(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_extract.py"

        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            check=True,
            text=True,
            capture_output=True,
        )

        self.assertIn("Extract one source", result.stdout)
        self.assertIn("--allow-duplicate", result.stdout)

    def _text_file(self, text: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return write_text_source(temp_dir.name, "profile.txt", text)


if __name__ == "__main__":
    unittest.main()
