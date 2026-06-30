import unittest

from app.wiki.dashboard_forms import safe_upload_filename


class WikiDashboardFormTests(unittest.TestCase):
    def test_safe_upload_filename_replaces_dot_segments(self):
        self.assertEqual("upload", safe_upload_filename("."))
        self.assertEqual("upload", safe_upload_filename(".."))
        self.assertEqual("note.txt", safe_upload_filename("../note.txt"))


if __name__ == "__main__":
    unittest.main()
