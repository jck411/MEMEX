import unittest

from app.wiki.dashboard_forms import parse_multipart_form, safe_upload_filename


class WikiDashboardFormTests(unittest.TestCase):
    def test_parse_multipart_form_reads_fields_and_files(self):
        boundary = "----memex-test-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="title"\r\n\r\n'
            "Career\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="source_file"; filename="../note.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            "Alice joined Example Co.\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        form = parse_multipart_form(f"multipart/form-data; boundary={boundary}", body)

        self.assertEqual("Career", form.first("title"))
        uploaded = form.file("source_file")
        self.assertIsNotNone(uploaded)
        assert uploaded is not None
        self.assertEqual("source_file", uploaded.field_name)
        self.assertEqual("note.txt", uploaded.file_name)
        self.assertEqual("text/plain", uploaded.content_type)
        self.assertEqual(b"Alice joined Example Co.", uploaded.data)

    def test_safe_upload_filename_replaces_dot_segments(self):
        self.assertEqual("upload", safe_upload_filename("."))
        self.assertEqual("upload", safe_upload_filename(".."))
        self.assertEqual("note.txt", safe_upload_filename("../note.txt"))


if __name__ == "__main__":
    unittest.main()
