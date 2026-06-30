import os
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


class DashboardProcessTests(unittest.TestCase):
    def test_require_canonical_dashboard_port_accepts_canonical(self):
        self.assertEqual(8765, dashboard_processes.require_canonical_dashboard_port(8765))

    def test_require_canonical_dashboard_port_rejects_alternate(self):
        with self.assertRaisesRegex(ValueError, "canonical port 8765"):
            dashboard_processes.require_canonical_dashboard_port(9999)

    def test_is_memex_dashboard_process_rejects_non_wiki_dev_command(self):
        root = Path("/home/jack/MEMEX")
        self.assertFalse(
            dashboard_processes.is_memex_dashboard_process(
                "/usr/bin/python3 scripts/other.py serve-dashboard",
                root,
                None,
            )
        )

    def test_is_memex_dashboard_process_rejects_command_without_serve_dashboard(self):
        root = Path("/home/jack/MEMEX")
        self.assertFalse(
            dashboard_processes.is_memex_dashboard_process(
                "/usr/bin/python3 scripts/wiki_dev.py model-profiles",
                root,
                None,
            )
        )

    def test_is_memex_dashboard_process_accepts_absolute_script_path(self):
        root = Path("/home/jack/MEMEX")
        command = "/home/jack/MEMEX/.venv/bin/python3 /home/jack/MEMEX/scripts/wiki_dev.py serve-dashboard"
        self.assertTrue(
            dashboard_processes.is_memex_dashboard_process(command, root, None)
        )

    def test_is_memex_dashboard_process_accepts_relative_path_inside_repo(self):
        root = Path("/home/jack/MEMEX")
        cwd = root / "scripts"
        command = "/home/jack/MEMEX/.venv/bin/python3 wiki_dev.py serve-dashboard"
        self.assertTrue(
            dashboard_processes.is_memex_dashboard_process(command, root, cwd)
        )

    def test_is_memex_dashboard_process_rejects_relative_path_outside_repo(self):
        root = Path("/home/jack/MEMEX")
        cwd = Path("/tmp")
        command = "/usr/bin/python3 wiki_dev.py serve-dashboard"
        self.assertFalse(
            dashboard_processes.is_memex_dashboard_process(command, root, cwd)
        )

    def test_cleanup_targets_skips_own_pid(self):
        root = Path("/home/jack/MEMEX")
        command = (
            "/home/jack/MEMEX/.venv/bin/python3 scripts/wiki_dev.py serve-dashboard"
        )
        own_pid = os.getpid()

        with (
            patch.object(
                dashboard_processes,
                "process_commands",
                return_value={own_pid: command},
            ),
            patch.object(dashboard_processes, "process_cwds", return_value={}),
            patch.object(
                dashboard_processes,
                "pids_listening_on_port",
                return_value=set(),
            ),
        ):
            self.assertEqual({}, dashboard_processes.cleanup_targets(root, 8765))

    def test_cleanup_targets_merges_command_matches_and_port_listeners(self):
        root = Path("/home/jack/MEMEX")
        command_match = (
            "/home/jack/MEMEX/.venv/bin/python3 scripts/wiki_dev.py serve-dashboard"
        )
        command_other = "/usr/bin/python3 some_other_process"

        with (
            patch.object(
                dashboard_processes,
                "process_commands",
                return_value={111: command_match, 222: command_other, 333: ""},
            ),
            patch.object(
                dashboard_processes,
                "process_cwds",
                return_value={111: root, 222: root, 333: root},
            ),
            patch.object(
                dashboard_processes,
                "pids_listening_on_port",
                return_value={222, 444},
            ),
        ):
            targets = dashboard_processes.cleanup_targets(root, 8765)

        self.assertEqual({111: command_match}, {k: v for k, v in targets.items() if k == 111})
        self.assertIn(222, targets)
        self.assertIn(444, targets)
        self.assertNotIn(333, targets)

    def test_listening_socket_inodes_filters_listen_state_and_port(self):
        # 0x223D == 8765 (canonical dashboard port).
        proc_net_tcp = (
            "  sl  local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt  uid  timeout inode\n"
            "   0: 0100007F:223D 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 12345 1 0000000000000000\n"
            "   1: 0100007F:2328 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 67890 1 0000000000000000\n"
            "   2: 0100007F:223D 0100007F:8000 06 00000000:00000000 00:00000000 00000000 0 0 99999 1 0000000000000000\n"
        )

        def fake_exists(self):
            return self.name == "tcp"

        def fake_read_text(self, encoding="utf-8"):
            return proc_net_tcp

        with (
            patch.object(Path, "exists", autospec=True, side_effect=fake_exists),
            patch.object(Path, "read_text", autospec=True, side_effect=fake_read_text),
        ):
            inodes = dashboard_processes.listening_socket_inodes(8765)

        # line 1: port 8765 + LISTEN -> 12345
        # line 2: port 9000 + LISTEN -> excluded (wrong port)
        # line 3: port 8765 + ESTABLISHED -> excluded (not LISTEN)
        self.assertEqual({"12345"}, inodes)

    def test_listening_socket_inodes_returns_empty_when_proc_net_missing(self):
        with patch.object(Path, "exists", autospec=True, return_value=False):
            self.assertEqual(set(), dashboard_processes.listening_socket_inodes(8765))

    def test_pids_listening_on_port_maps_inode_to_pid(self):
        proc_entries = [Path("/proc/111"), Path("/proc/abc"), Path("/proc/222")]
        fds_for = {
            "111": [Path("/proc/111/fd/3"), Path("/proc/111/fd/4")],
            "222": [Path("/proc/222/fd/7")],
        }
        readlinks = {
            Path("/proc/111/fd/3"): "socket:[12345]",  # match
            Path("/proc/111/fd/4"): "socket:[99999]",  # inode not listening
            Path("/proc/222/fd/7"): "socket:[67890]",  # inode not in our set
        }

        def fake_iterdir(self):
            if self == Path("/proc"):
                return proc_entries
            if str(self).startswith("/proc/") and self.name == "fd":
                return fds_for.get(self.parent.name, [])
            return []

        def fake_readlink(path):
            return readlinks.get(path, "")

        with (
            patch.object(Path, "iterdir", autospec=True, side_effect=fake_iterdir),
            patch("os.readlink", side_effect=fake_readlink),
            patch.object(
                dashboard_processes,
                "listening_socket_inodes",
                return_value={"12345"},
            ),
        ):
            pids = dashboard_processes.pids_listening_on_port(8765)

        self.assertEqual({111}, pids)

    def test_pids_listening_on_port_returns_empty_when_no_inodes(self):
        with patch.object(
            dashboard_processes,
            "listening_socket_inodes",
            return_value=set(),
        ):
            self.assertEqual(set(), dashboard_processes.pids_listening_on_port(8765))


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
