import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.wiki.extraction_contract import (
    EXTRACTION_SCHEMA_NAME,
    anthropic_extraction_output_format,
    extraction_json_schema,
    extraction_model_json_schema,
    openai_extraction_text_format,
    provider_extraction_json_schema,
)
from app.wiki.model_profiles import (
    DEFAULT_EXTRACTION_MODEL_PROFILES,
    DEFAULT_EXTRACTION_PROFILE_ID,
    enabled_extraction_model_profiles,
    extraction_model_readiness,
    extraction_profile_for_source_type,
    extraction_route_for_source_type,
    load_env_file,
    model_profile_readiness,
)


class WikiModelProfileTests(unittest.TestCase):
    def test_default_profiles_compare_direct_providers(self):
        profile_ids = tuple(profile.profile_id for profile in DEFAULT_EXTRACTION_MODEL_PROFILES)

        self.assertEqual(
            (
                "anthropic:claude-sonnet-4-6",
                "openai:gpt-5.5",
                "google:gemini-3.5-flash",
            ),
            profile_ids,
        )
        self.assertEqual("anthropic:claude-sonnet-4-6", DEFAULT_EXTRACTION_PROFILE_ID)
        self.assertIn("input_schema", DEFAULT_EXTRACTION_MODEL_PROFILES[0].structured_output)
        self.assertIn("json_schema", DEFAULT_EXTRACTION_MODEL_PROFILES[1].structured_output)
        self.assertIn("responseMimeType", DEFAULT_EXTRACTION_MODEL_PROFILES[2].structured_output)
        self.assertTrue(all(profile.enabled for profile in DEFAULT_EXTRACTION_MODEL_PROFILES))
        self.assertTrue(all(profile.schema_strict for profile in DEFAULT_EXTRACTION_MODEL_PROFILES))

    def test_default_routes_choose_one_extractor_per_format_family(self):
        self.assertEqual(
            "anthropic:claude-sonnet-4-6",
            extraction_profile_for_source_type("pdf").profile_id,
        )
        self.assertEqual(
            "anthropic:claude-sonnet-4-6",
            extraction_profile_for_source_type(".png").profile_id,
        )
        self.assertEqual(
            "anthropic:claude-sonnet-4-6",
            extraction_profile_for_source_type("markdown").profile_id,
        )
        self.assertEqual(
            "anthropic:claude-sonnet-4-6",
            extraction_profile_for_source_type("xlsx").profile_id,
        )
        self.assertIsNone(extraction_route_for_source_type("unknown-format"))
        self.assertEqual(
            (
                "anthropic:claude-sonnet-4-6",
                "openai:gpt-5.5",
                "google:gemini-3.5-flash",
            ),
            tuple(profile.profile_id for profile in enabled_extraction_model_profiles()),
        )

    def test_extraction_json_schema_is_shared_across_direct_providers(self):
        schema = extraction_json_schema()

        self.assertEqual("object", schema["type"])
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("document", schema["required"])
        self.assertIn("evidence", schema["required"])
        self.assertIn("run", schema["required"])
        self.assertIn("facts", schema["required"])
        fact_schema = schema["properties"]["facts"]["items"]
        self.assertNotIn("sensitivity", fact_schema["properties"])
        self.assertNotIn("sensitivity", fact_schema["required"])
        self.assertNotIn("run", extraction_model_json_schema()["required"])
        self.assertNotIn("$schema", provider_extraction_json_schema())
        self.assertNotIn("title", provider_extraction_json_schema())
        self.assertEqual(EXTRACTION_SCHEMA_NAME, openai_extraction_text_format()["name"])
        self.assertTrue(openai_extraction_text_format()["strict"])
        self.assertEqual(
            provider_extraction_json_schema(),
            anthropic_extraction_output_format()["schema"],
        )

    def test_env_file_loading_and_readiness_do_not_require_real_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                (
                    "OPENAI_API_KEY='openai-test'\n"
                    "ANTHROPIC_API_KEY=anthropic-test\n"
                    "GEMINI_API_KEY=gemini-test\n"
                ),
                encoding="utf-8",
            )
            env = load_env_file(env_path)

            readiness = extraction_model_readiness(env)

            self.assertEqual("openai-test", env["OPENAI_API_KEY"])
            self.assertEqual("gemini-test", env["GEMINI_API_KEY"])
            self.assertTrue(all(item.configured for item in readiness))

    def test_missing_env_key_is_reported_without_secret_values(self):
        profile = DEFAULT_EXTRACTION_MODEL_PROFILES[1]

        readiness = model_profile_readiness(profile, {})

        self.assertFalse(readiness.configured)
        self.assertEqual("OPENAI_API_KEY", readiness.missing_env_key)

    def test_cli_model_profiles_reports_configuration_without_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("OPENAI_API_KEY=secret-value\n", encoding="utf-8")
            script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_dev.py"

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--repo-root",
                    temp_dir,
                    "model-profiles",
                    "--env-file",
                    str(env_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            self.assertIn(
                "anthropic:claude-sonnet-4-6\tconfigured=missing ANTHROPIC_API_KEY\tenabled=yes",
                result.stdout,
            )
            self.assertIn("openai:gpt-5.5\tconfigured=yes\tenabled=yes", result.stdout)
            self.assertIn(
                "google:gemini-3.5-flash\tconfigured=missing GEMINI_API_KEY\tenabled=yes",
                result.stdout,
            )
            self.assertIn("schema: memex_wiki_prep_extraction strict=yes", result.stdout)
            self.assertIn("default routes: pdf, image, text, office, spreadsheet", result.stdout)
            self.assertIn("default routes: none", result.stdout)
            self.assertNotIn("secret-value", result.stdout)


if __name__ == "__main__":
    unittest.main()
