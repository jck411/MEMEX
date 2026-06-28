#!/usr/bin/env python3
"""Start the MEMEX dashboard after clearing stale local server processes."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
TERMINATE_TIMEOUT_SECONDS = 2.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fresh-start the local MEMEX dashboard server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be killed and started without changing processes",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    targets = cleanup_targets(Path(args.repo_root), args.port)
    if targets:
        print(_target_summary("clearing", targets))
    else:
        print("no existing MEMEX dashboard process found")

    command = server_command(
        Path(args.repo_root),
        host=args.host,
        port=args.port,
        env_file=args.env_file,
    )
    if args.dry_run:
        print("would start: " + " ".join(command))
        return 0

    terminate_processes(tuple(targets))
    print(f"starting MEMEX dashboard at http://{args.host}:{args.port}/")
    os.execv(sys.executable, command)
    return 0


def server_command(
    repo_root: Path,
    *,
    host: str,
    port: int,
    env_file: str,
) -> list[str]:
    return [
        sys.executable,
        str(repo_root / "scripts" / "wiki_dev.py"),
        "--repo-root",
        str(repo_root),
        "serve-dashboard",
        "--host",
        host,
        "--port",
        str(port),
        "--env-file",
        env_file,
    ]


def cleanup_targets(repo_root: Path, port: int) -> dict[int, str]:
    targets: dict[int, str] = {}
    for pid, command in process_commands().items():
        if pid == os.getpid():
            continue
        if is_memex_dashboard_command(command, repo_root):
            targets[pid] = command
    for pid in pids_listening_on_port(port):
        if pid == os.getpid():
            continue
        targets.setdefault(pid, process_commands().get(pid, f"pid {pid}"))
    return targets


def terminate_processes(targets: tuple[int, ...]) -> None:
    live = [pid for pid in targets if _process_exists(pid)]
    for pid in live:
        _signal_process(pid, signal.SIGTERM)

    deadline = time.monotonic() + TERMINATE_TIMEOUT_SECONDS
    while live and time.monotonic() < deadline:
        live = [pid for pid in live if _process_exists(pid)]
        if live:
            time.sleep(0.05)

    for pid in live:
        _signal_process(pid, signal.SIGKILL)


def is_memex_dashboard_command(command: str, repo_root: Path) -> bool:
    normalized = command.replace("\\", "/")
    script = str(repo_root / "scripts" / "wiki_dev.py").replace("\\", "/")
    return script in normalized and "serve-dashboard" in normalized


def process_commands() -> dict[int, str]:
    commands: dict[int, str] = {}
    proc_root = Path("/proc")
    if proc_root.exists():
        for entry in proc_root.iterdir():
            if not entry.name.isdigit():
                continue
            command = _proc_cmdline(entry / "cmdline")
            if command:
                commands[int(entry.name)] = command
        return commands

    output = subprocess.run(
        ["ps", "-eo", "pid=,args="],
        check=False,
        capture_output=True,
        text=True,
    )
    for line in output.stdout.splitlines():
        pid_text, _, command = line.strip().partition(" ")
        if pid_text.isdigit() and command:
            commands[int(pid_text)] = command
    return commands


def pids_listening_on_port(port: int) -> set[int]:
    inodes = listening_socket_inodes(port)
    if not inodes:
        return set()
    pids: set[int] = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        fd_dir = entry / "fd"
        try:
            fds = tuple(fd_dir.iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if target.startswith("socket:[") and target[8:-1] in inodes:
                pids.add(int(entry.name))
                break
    return pids


def listening_socket_inodes(port: int) -> set[str]:
    inodes: set[str] = set()
    for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        if not table.exists():
            continue
        for line in table.read_text(encoding="utf-8").splitlines()[1:]:
            fields = line.split()
            if len(fields) < 10:
                continue
            local_address = fields[1]
            state = fields[3]
            inode = fields[9]
            _, _, port_hex = local_address.rpartition(":")
            if state == "0A" and int(port_hex, 16) == port:
                inodes.add(inode)
    return inodes


def _proc_cmdline(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    return " ".join(part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part)


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_process(pid: int, sig: signal.Signals) -> None:
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return


def _target_summary(action: str, targets: dict[int, str]) -> str:
    lines = [f"{action} {len(targets)} existing process(es):"]
    for pid, command in sorted(targets.items()):
        lines.append(f"  {pid}: {command}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
