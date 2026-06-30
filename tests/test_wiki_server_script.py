import subprocess
import sys
import unittest
from importlib import util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.wiki import dashboard_processes


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
        root = Path("/home/jack/MEMEX")
        command = (
            "/home/jack/MEMEX/.venv/bin/python3 "
            "scripts/wiki_dev.py serve-dashboard --host 127.0.0.1 --port 8766"
        )

        with (
            patch.object(dashboard_processes, "process_commands", return_value={123: command}),
            patch.object(dashboard_processes, "process_cwds", return_value={123: root}),
            patch.object(dashboard_processes, "pids_listening_on_port", return_value=set()),
        ):
            self.assertEqual({123: command}, dashboard_processes.cleanup_targets(root, 8765))

    def test_dev_script_rejects_alternate_dashboard_port(self):
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "wiki_dev.py"

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "serve-dashboard",
                "--port",
                "9999",
            ],
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("canonical port 8765", result.stderr)

    def test_dev_serve_dashboard_clears_existing_processes_before_serving(self):
        module = _load_script("wiki_dev_for_test", "wiki_dev.py")
        root = Path(__file__).resolve().parents[1]
        args = SimpleNamespace(
            repo_root=str(root),
            env_file=None,
            host="127.0.0.1",
            port=8765,
        )

        with (
            patch.object(module, "cleanup_targets", return_value={123: "old dashboard"}),
            patch.object(module, "terminate_processes") as terminate,
            patch.object(module, "run_dashboard_server") as run_server,
        ):
            self.assertEqual(0, module._run_serve_dashboard(args, object()))

        terminate.assert_called_once_with((123,))
        run_server.assert_called_once()


def _load_script(module_name: str, script_name: str):
    root = Path(__file__).resolve().parents[1]
    spec = util.spec_from_file_location(
        module_name,
        root / "scripts" / script_name,
    )
    if spec is None or spec.loader is None:  # pragma: no cover
        raise AssertionError(f"failed to load {script_name}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
