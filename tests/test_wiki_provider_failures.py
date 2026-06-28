import unittest
from io import BytesIO
from urllib.error import HTTPError

from app.wiki.anthropic_extraction import AnthropicSourceExtractor
from app.wiki.extraction_inputs import ExtractionInput
from app.wiki.extraction_packets import ExtractionPacketError
from app.wiki.google_extraction import GoogleSourceExtractor
from app.wiki.openai_extraction import OpenAISourceExtractor
from tests.helpers import RawResponse


class WikiProviderFailureTests(unittest.TestCase):
    def test_extractors_surface_http_failures_as_packet_errors(self):
        for label, factory in _extractor_factories():
            with self.subTest(provider=label):

                def opener(request, timeout):
                    raise HTTPError(
                        request.full_url,
                        503,
                        "Service Unavailable",
                        {},
                        BytesIO(b"provider down"),
                    )

                with self.assertRaisesRegex(
                    ExtractionPacketError,
                    f"{label} returned HTTP 503: provider down",
                ):
                    factory(opener).extract(_source_input(label))

    def test_extractors_surface_malformed_transport_json_as_packet_errors(self):
        for label, factory in _extractor_factories():
            with self.subTest(provider=label):

                def opener(request, timeout):
                    return RawResponse(b"not-json")

                with self.assertRaisesRegex(
                    ExtractionPacketError,
                    f"{label} response was not JSON",
                ):
                    factory(opener).extract(_source_input(label))


def _extractor_factories():
    return (
        (
            "Anthropic",
            lambda opener: AnthropicSourceExtractor(api_key="secret", opener=opener),
        ),
        (
            "OpenAI",
            lambda opener: OpenAISourceExtractor(api_key="secret", opener=opener),
        ),
        (
            "Google",
            lambda opener: GoogleSourceExtractor(api_key="secret", opener=opener),
        ),
    )


def _source_input(provider: str) -> ExtractionInput:
    return ExtractionInput(
        source_id=f"source-{provider.lower()}",
        source_text="Alice joined Example Co.",
    )


if __name__ == "__main__":
    unittest.main()
