import json
import unittest

from app.wiki.extraction_inputs import ExtractionAttachment, ExtractionInput
from app.wiki.openai_extraction import OPENAI_RESPONSES_URL, OpenAISourceExtractor
from tests.helpers import JsonResponse, extraction_packet


def _packet(source_id: str):
    return extraction_packet(source_id)


class WikiOpenAIExtractionTests(unittest.TestCase):
    def test_openai_extractor_uses_responses_schema_and_input_file_parts(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return JsonResponse(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(_packet("source-openai")),
                                }
                            ],
                        }
                    ],
                    "usage": {"input_tokens": 11, "output_tokens": 22},
                }
            )

        result = OpenAISourceExtractor(
            api_key="secret",
            model="gpt-5.5",
            opener=opener,
        ).extract(
            ExtractionInput(
                "source-openai",
                source_text="Alice joined Example Co.",
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

        self.assertEqual(OPENAI_RESPONSES_URL, seen["url"])
        self.assertEqual("Bearer secret", seen["auth"])
        self.assertEqual("gpt-5.5", seen["body"]["model"])
        self.assertEqual(
            "json_schema",
            seen["body"]["text"]["format"]["type"],
        )
        content = seen["body"]["input"][1]["content"]
        self.assertEqual("input_text", content[0]["type"])
        self.assertEqual("input_image", content[1]["type"])
        self.assertTrue(content[1]["image_url"].startswith("data:image/png;base64,"))
        self.assertEqual("input_file", content[2]["type"])
        self.assertEqual("document.pdf", content[2]["filename"])
        self.assertTrue(content[2]["file_data"].startswith("data:application/pdf;base64,"))
        self.assertEqual("source-openai", result.source.source_id)
        self.assertEqual("openai", result.packet["run"]["provider"])
        self.assertEqual({"input_tokens": 11, "output_tokens": 22}, result.usage)


if __name__ == "__main__":
    unittest.main()
