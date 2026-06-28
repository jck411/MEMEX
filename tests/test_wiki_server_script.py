import subprocess
import sys
import unittest
from pathlib import Path


class WikiServerScriptTests(unittest.TestCase):
    def test_server_script_dry_run_resolves_dashboard_command(self):
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "wiki_server.py"

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--dry-run",
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ],
            check=True,
            text=True,
            capture_output=True,
        )

        self.assertIn("would start:", result.stdout)
        self.assertIn("scripts/wiki_dev.py", result.stdout)
        self.assertIn("serve-dashboard", result.stdout)
        self.assertIn("--port 8765", result.stdout)


if __name__ == "__main__":
    unittest.main()
