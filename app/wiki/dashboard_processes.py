"""Canonical local dashboard process policy."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8765
TERMINATE_TIMEOUT_SECONDS = 2.0


def require_canonical_dashboard_port(port: int) -> int:
    if port != DASHBOARD_PORT:
        raise ValueError(f"MEMEX dashboard must run on canonical port {DASHBOARD_PORT}")
    return port


def cleanup_targets(repo_root: Path, port: int = DASHBOARD_PORT) -> dict[int, str]:
    repo_root = repo_root.resolve(strict=False)
    commands = process_commands()
    cwds = process_cwds()
    targets: dict[int, str] = {}
    for pid, command in commands.items():
        if pid == os.getpid():
            continue
        if is_memex_dashboard_process(command, repo_root, cwds.get(pid)):
            targets[pid] = command
    for pid in pids_listening_on_port(port):
        if pid == os.getpid():
            continue
        targets.setdefault(pid, commands.get(pid, f"pid {pid}"))
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


def target_summary(action: str, targets: dict[int, str]) -> str:
    lines = [f"{action} {len(targets)} existing process(es):"]
    for pid, command in sorted(targets.items()):
        lines.append(f"  {pid}: {command}")
    return "\n".join(lines)


def is_memex_dashboard_command(command: str, repo_root: Path) -> bool:
    return is_memex_dashboard_process(command, repo_root.resolve(strict=False), None)


def is_memex_dashboard_process(
    command: str,
    repo_root: Path,
    cwd: Path | None,
) -> bool:
    normalized = command.replace("\\", "/")
    if "serve-dashboard" not in normalized or "wiki_dev.py" not in normalized:
        return False
    script = str(repo_root / "scripts" / "wiki_dev.py").replace("\\", "/")
    if script in normalized:
        return True
    if cwd is None:
        return False
    return _path_is_inside(cwd.resolve(strict=False), repo_root) and (
        "scripts/wiki_dev.py" in normalized or "wiki_dev.py" in normalized
    )


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


def process_cwds() -> dict[int, Path]:
    cwds: dict[int, Path] = {}
    proc_root = Path("/proc")
    if not proc_root.exists():
        return cwds
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        cwd = _proc_cwd(entry / "cwd")
        if cwd is not None:
            cwds[int(entry.name)] = cwd
    return cwds


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


def _proc_cwd(path: Path) -> Path | None:
    try:
        return Path(os.readlink(path)).resolve(strict=False)
    except OSError:
        return None


def _path_is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


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
    except PermissionError:
        return
