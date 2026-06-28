import json
import unittest

from app.wiki.extraction_inputs import ExtractionAttachment, ExtractionInput
from app.wiki.google_extraction import (
    GOOGLE_GENERATE_CONTENT_BASE_URL,
    GoogleSourceExtractor,
)
from tests.helpers import JsonResponse, extraction_packet


def _packet(source_id: str):
    return extraction_packet(source_id, title="Profile Image", source_type="image", locator="image text")


class WikiGoogleExtractionTests(unittest.TestCase):
    def test_google_extractor_uses_generate_content_schema_and_inline_attachments(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["api_key"] = request.get_header("X-goog-api-key")
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return JsonResponse(
                {
                    "candidates": [
                        {"content": {"parts": [{"text": json.dumps(_packet("source-google"))}]}}
                    ],
                    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
                }
            )

        result = GoogleSourceExtractor(
            api_key="secret",
            model="gemini-3.5-flash",
            opener=opener,
        ).extract(
            ExtractionInput(
                "source-google",
                title="Profile Image",
                source_type="image",
                attachments=(
                    ExtractionAttachment(
                        "scan.png",
                        "image/png",
                        "aW1hZ2U=",
                    ),
                    ExtractionAttachment(
                        "document.pdf",
                        "application/pdf",
                        "cGRm",
                    ),
                ),
            )
        )

        self.assertEqual(
            f"{GOOGLE_GENERATE_CONTENT_BASE_URL}/gemini-3.5-flash:generateContent",
            seen["url"],
        )
        self.assertEqual("secret", seen["api_key"])
        self.assertEqual(
            "application/json",
            seen["body"]["generationConfig"]["responseMimeType"],
        )
        self.assertIn("responseJsonSchema", seen["body"]["generationConfig"])
        parts = seen["body"]["contents"][0]["parts"]
        self.assertIn("source-google", parts[0]["text"])
        self.assertEqual(
            {"mime_type": "image/png", "data": "aW1hZ2U="},
            parts[1]["inline_data"],
        )
        self.assertEqual(
            {"mime_type": "application/pdf", "data": "cGRm"},
            parts[2]["inline_data"],
        )
        self.assertEqual("source-google", result.source.source_id)
        self.assertEqual("google", result.packet["run"]["provider"])
        self.assertEqual(
            {"promptTokenCount": 10, "candidatesTokenCount": 20},
            result.usage,
        )


if __name__ == "__main__":
    unittest.main()
