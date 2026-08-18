"""Safe, read-only access to Markdown files inside an Obsidian vault."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

CONTROL_FILES = {
    "flag_fetch.md",
    "flag_rebuild.md",
    "redflag.md",
    "redflag2.md",
    "redflag3.md",
}
CONTROL_DIRECTORIES = {".git", ".livesync", ".obsidian"}
DEFAULT_LIMIT = 100
MAX_LIMIT = 500
DEFAULT_READ_LINES = 400
MAX_READ_LINES = 2_000


class Vault:
    """Enumerate, read, and search user Markdown without leaving the vault root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def list_markdown(
        self,
        path_prefix: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """List Markdown files, optionally below a vault-relative directory."""
        safe_limit = self._limit(limit)
        prefix = self._prefix(path_prefix)
        files = [item for item in self._markdown_files() if self._matches_prefix(item, prefix)]
        selected = files[:safe_limit]
        return {
            "count": len(selected),
            "total": len(files),
            "truncated": len(selected) < len(files),
            "files": [self._metadata(path) for path in selected],
        }

    def read_markdown(
        self,
        path: str,
        start_line: int = 1,
        max_lines: int = DEFAULT_READ_LINES,
    ) -> dict[str, Any]:
        """Read a Markdown file in bounded, line-addressable chunks."""
        target = self._markdown_path(path)
        if start_line < 1:
            raise ValueError("start_line must be at least 1")
        safe_max_lines = self._limit(max_lines, maximum=MAX_READ_LINES)
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = min(start_line - 1, len(lines))
        end = min(start + safe_max_lines, len(lines))
        return {
            "path": self._relative(target),
            "start_line": start + 1 if lines else 0,
            "end_line": end,
            "total_lines": len(lines),
            "truncated": end < len(lines),
            "content": "\n".join(lines[start:end]),
        }

    def search_markdown(
        self,
        query: str,
        path_prefix: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Find case-insensitive literal matches across every vault Markdown file."""
        needle = query.strip().casefold()
        if not needle:
            raise ValueError("query must not be empty")
        if len(needle) > 500:
            raise ValueError("query must be at most 500 characters")
        safe_limit = self._limit(limit)
        prefix = self._prefix(path_prefix)
        matches: list[dict[str, Any]] = []
        for path in self._markdown_files():
            if not self._matches_prefix(path, prefix):
                continue
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
            ):
                if needle not in line.casefold():
                    continue
                matches.append(
                    {
                        "path": self._relative(path),
                        "line": line_number,
                        "text": line.strip()[:500],
                    }
                )
                if len(matches) == safe_limit:
                    return {
                        "query": query,
                        "count": len(matches),
                        "truncated": True,
                        "matches": matches,
                    }
        return {
            "query": query,
            "count": len(matches),
            "truncated": False,
            "matches": matches,
        }

    def recent_markdown(self, limit: int = 20) -> dict[str, Any]:
        """List Markdown files from newest to oldest modification time."""
        safe_limit = self._limit(limit)
        files = sorted(self._markdown_files(), key=lambda path: path.stat().st_mtime, reverse=True)
        selected = files[:safe_limit]
        return {
            "count": len(selected),
            "total": len(files),
            "truncated": len(selected) < len(files),
            "files": [self._metadata(path) for path in selected],
        }

    def status(self) -> dict[str, Any]:
        """Report vault readability and latest visible Markdown modification."""
        if not self.root.is_dir():
            return {"status": "unavailable", "markdown_count": 0}
        files = self._markdown_files()
        newest = max((path.stat().st_mtime for path in files), default=None)
        return {
            "status": "ok",
            "markdown_count": len(files),
            "latest_markdown_modified": self._timestamp(newest) if newest is not None else None,
        }

    def _markdown_files(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        files: list[Path] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.casefold() != ".md":
                continue
            relative = path.relative_to(self.root)
            if self._is_control_path(relative):
                continue
            resolved = path.resolve()
            if self._is_within_root(resolved):
                files.append(resolved)
        return sorted(files, key=self._relative)

    def _markdown_path(self, value: str) -> Path:
        relative = self._relative_input(value)
        if relative.suffix.casefold() != ".md":
            raise ValueError("path must identify a Markdown file")
        if self._is_control_path(relative):
            raise ValueError("path identifies Obsidian or LiveSync control state")
        target = (self.root / relative).resolve()
        if not self._is_within_root(target):
            raise ValueError("path escapes the vault")
        if not target.is_file():
            raise FileNotFoundError(f"Markdown file not found: {relative.as_posix()}")
        return target

    def _prefix(self, value: str) -> PurePosixPath | None:
        if not value.strip():
            return None
        prefix = self._relative_input(value)
        if self._is_control_path(prefix):
            raise ValueError("path_prefix identifies Obsidian or LiveSync control state")
        return prefix

    @staticmethod
    def _relative_input(value: str) -> PurePosixPath:
        normalized = value.strip().replace("\\", "/")
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts:
            raise ValueError("path must be vault-relative and must not contain '..'")
        return path

    @staticmethod
    def _limit(value: int, maximum: int = MAX_LIMIT) -> int:
        if value < 1 or value > maximum:
            raise ValueError(f"limit must be between 1 and {maximum}")
        return value

    @staticmethod
    def _is_control_path(relative: PurePosixPath) -> bool:
        return (
            relative.name.casefold() in CONTROL_FILES
            or any(part.casefold() in CONTROL_DIRECTORIES for part in relative.parts)
        )

    def _matches_prefix(self, path: Path, prefix: PurePosixPath | None) -> bool:
        if prefix is None:
            return True
        relative = PurePosixPath(self._relative(path))
        return relative.parts[: len(prefix.parts)] == prefix.parts

    def _is_within_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.root)
        except ValueError:
            return False
        return True

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _metadata(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        return {
            "path": self._relative(path),
            "size_bytes": stat.st_size,
            "modified": self._timestamp(stat.st_mtime),
        }

    @staticmethod
    def _timestamp(value: float) -> str:
        return datetime.fromtimestamp(value, tz=UTC).isoformat()
