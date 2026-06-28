import tempfile
from pathlib import Path

from app.wiki.dashboard_server import create_dashboard_server
from app.wiki.model_profiles import DEFAULT_EXTRACTION_PROFILE_ID
from app.wiki.source_extraction import SourceExtractionWorkflowResult
from tests.dashboard_server_helpers import DashboardServerTestCase
from tests.helpers import fact_record, source_record, wiki_workspace
from tests.html_helpers import parse_html


class WikiDashboardServerIngestTests(DashboardServerTestCase):
    def test_dashboard_server_uploads_source_file_without_assignment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            seen = {}

            def extract_source(job):
                seen["job"] = job
                seen["file_text"] = Path(job.path).read_text(encoding="utf-8")
                source = source_record(
                    job.source_id,
                    fact_record("fact-upload", "Uploaded source fact."),
                    title=job.title,
                    source_type=job.source_type,
                )
                workspace.save_source(source)
                return SourceExtractionWorkflowResult(
                    source=source,
                    model_spec=job.model_spec,
                    usage={},
                )

            server = create_dashboard_server(
                workspace,
                port=0,
                source_extractor=extract_source,
                extraction_model_spec=DEFAULT_EXTRACTION_PROFILE_ID,
            )
            with self.serving(server) as (host, port):
                body = self.request(host, port, "GET", "/")[2]
                page = parse_html(body)
                page.require("form", {"method": "post", "action": "/upload"})
                self.assertEqual(0, page.count("form", {"action": "/extract"}))

                status, location, _ = self.multipart_request(
                    host,
                    port,
                    "/upload",
                    {"model_spec": DEFAULT_EXTRACTION_PROFILE_ID},
                    {
                        "source_file": (
                            "Profile Note.txt",
                            "text/plain",
                            b"Uploaded source fact.",
                        )
                    },
                )

                self.assertEqual(303, status)
                self.assertTrue(location.startswith("/?message="))
                self.assertNotIn("/source/profile-note", location)
                self.assertIn("extracted+profile-note", location)
                self.assertEqual("profile-note", seen["job"].source_id)
                self.assertEqual("", seen["job"].title)
                self.assertEqual("", seen["job"].source_type)
                self.assertEqual(DEFAULT_EXTRACTION_PROFILE_ID, seen["job"].model_spec)
                self.assertEqual("file", seen["job"].source_kind)
                self.assertEqual("text/plain", seen["job"].mime_type)
                self.assertFalse(seen["job"].allow_duplicate)
                self.assertEqual("Uploaded source fact.", seen["file_text"])
                self.assertTrue(workspace.status("career").current)
                self.assertEqual((), workspace.data_store.load_ledger().assigned_sources("career"))

    def test_dashboard_server_upload_can_keep_duplicate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.save_source(
                source_record(
                    "profile-note-openai-gpt-5.5",
                    fact_record("fact-existing", "Earlier run."),
                    title="Existing duplicate",
                )
            )
            seen = {}

            def extract_source(job):
                seen["job"] = job
                source = source_record(
                    job.source_id,
                    fact_record("fact-upload", "Uploaded source fact."),
                    title="Duplicate",
                )
                workspace.save_source(source)
                return SourceExtractionWorkflowResult(
                    source=source,
                    model_spec=job.model_spec,
                    usage={},
                )

            server = create_dashboard_server(
                workspace,
                port=0,
                source_extractor=extract_source,
                extraction_model_spec=DEFAULT_EXTRACTION_PROFILE_ID,
            )
            with self.serving(server) as (host, port):
                status, location, _ = self.multipart_request(
                    host,
                    port,
                    "/upload",
                    {
                        "model_spec": "openai:gpt-5.5",
                        "allow_duplicate": "1",
                    },
                    {
                        "source_file": (
                            "Profile Note.txt",
                            "text/plain",
                            b"Uploaded source fact.",
                        )
                    },
                )

                self.assertEqual(303, status)
                self.assertTrue(location.startswith("/?message="))
                self.assertNotIn("/source/profile-note-openai-gpt-5.5-2", location)
                self.assertIn("profile-note-openai-gpt-5.5-2", location)
                self.assertEqual("profile-note-openai-gpt-5.5-2", seen["job"].source_id)
                self.assertEqual("openai:gpt-5.5", seen["job"].model_spec)
                self.assertTrue(seen["job"].allow_duplicate)

    def test_dashboard_server_upload_redirects_to_existing_source_for_duplicate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            existing = source_record(
                "source-existing",
                fact_record("fact-existing", "Existing source fact."),
                title="Existing",
            )
            workspace.save_source(existing)

            def extract_source(job):
                return SourceExtractionWorkflowResult(
                    source=existing,
                    model_spec=job.model_spec,
                    usage={},
                    duplicate_source_id=existing.source_id,
                )

            server = create_dashboard_server(
                workspace,
                port=0,
                source_extractor=extract_source,
                extraction_model_spec=DEFAULT_EXTRACTION_PROFILE_ID,
            )
            with self.serving(server) as (host, port):
                status, location, _ = self.multipart_request(
                    host,
                    port,
                    "/upload",
                    {},
                    {
                        "source_file": (
                            "Copy.txt",
                            "text/plain",
                            b"Existing source fact.",
                        )
                    },
                )

                self.assertEqual(303, status)
                self.assertTrue(location.startswith("/?message="))
                self.assertNotIn("/source/source-existing", location)
                self.assertIn(
                    "byte-identical+source+already+exists+as+source-existing",
                    location,
                )

    def test_dashboard_server_adds_typed_text_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            seen = {}

            def extract_source(job):
                seen["job"] = job
                seen["file_name"] = Path(job.path).name
                seen["file_text"] = Path(job.path).read_text(encoding="utf-8")
                source = source_record(
                    job.source_id,
                    fact_record("fact-text", "Typed source fact."),
                    title=job.title,
                    source_type=job.source_type,
                )
                workspace.save_source(source)
                return SourceExtractionWorkflowResult(
                    source=source,
                    model_spec=job.model_spec,
                    usage={},
                )

            server = create_dashboard_server(
                workspace,
                port=0,
                source_extractor=extract_source,
                extraction_model_spec=DEFAULT_EXTRACTION_PROFILE_ID,
            )
            with self.serving(server) as (host, port):
                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/text-source",
                    {
                        "text_title": "Meeting Note",
                        "source_text": "Typed source fact.",
                        "model_spec": DEFAULT_EXTRACTION_PROFILE_ID,
                    },
                )

                self.assertEqual(303, status)
                self.assertTrue(location.startswith("/?message="))
                self.assertNotIn("/source/meeting-note", location)
                self.assertIn("added+text+source", location)
                self.assertEqual("meeting-note", seen["job"].source_id)
                self.assertEqual("Meeting Note", seen["job"].title)
                self.assertEqual("text", seen["job"].source_type)
                self.assertEqual(DEFAULT_EXTRACTION_PROFILE_ID, seen["job"].model_spec)
                self.assertEqual("typed_text", seen["job"].source_kind)
                self.assertEqual("text/plain", seen["job"].mime_type)
                self.assertFalse(seen["job"].allow_duplicate)
                self.assertEqual("meeting-note.txt", seen["file_name"])
                self.assertEqual("Typed source fact.", seen["file_text"])
