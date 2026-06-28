import subprocess
import sys
import unittest
from importlib import util
from pathlib import Path
from unittest.mock import patch


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

    def test_server_script_rejects_alternate_dashboard_port(self):
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "wiki_server.py"

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--dry-run",
                "--port",
                "8766",
            ],
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("canonical port 8765", result.stderr)

    def test_cleanup_targets_detects_relative_dashboard_on_other_port(self):
        module = _load_server_script()
        root = Path("/home/jack/MEMEX")
        command = (
            "/home/jack/MEMEX/.venv/bin/python3 "
            "scripts/wiki_dev.py serve-dashboard --host 127.0.0.1 --port 8766"
        )

        with (
            patch.object(module, "process_commands", return_value={123: command}),
            patch.object(module, "process_cwds", return_value={123: root}),
            patch.object(module, "pids_listening_on_port", return_value=set()),
        ):
            self.assertEqual({123: command}, module.cleanup_targets(root, 8765))


def _load_server_script():
    root = Path(__file__).resolve().parents[1]
    spec = util.spec_from_file_location(
        "wiki_server_for_test",
        root / "scripts" / "wiki_server.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load wiki_server.py")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
