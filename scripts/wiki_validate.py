#!/usr/bin/env python3
"""Validate the filesystem-only MEMEX source and wiki layout."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

SOURCE_LINK_RE = re.compile(r"\[[^\]]*\]\((?P<target>[^)]+)\)")
RESERVED_CONTEXT_NAMES = {"sources", "temp"}


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    wiki_count: int
    source_count: int
    source_link_count: int
    inbox_count: int

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_repo(repo_root: str | Path) -> ValidationReport:
    root = Path(repo_root).resolve()
    vault = root / "vault"
    general_sources = vault / "Sources"
    inbox = general_sources / "Inbox"
    errors: list[str] = []
    warnings: list[str] = []

    if not vault.is_dir():
        errors.append("missing vault directory")
    if not general_sources.is_dir():
        errors.append("missing vault/Sources directory")
    if not inbox.is_dir():
        errors.append("missing vault/Sources/Inbox directory")

    context_roots = _context_roots(vault)
    wiki_entries = [
        (wiki_path, context_root, sources_root)
        for context_root in context_roots
        if (sources_root := context_root / "Sources").is_dir()
        for wiki_path in sorted(context_root.glob("*.md"))
        if (sources_root / wiki_path.stem).is_dir()
    ]
    referenced_sources: set[Path] = set()
    source_link_count = 0

    for wiki_path, context_root, sources_root in wiki_entries:
        wiki_label = wiki_path.relative_to(vault).as_posix()
        text = wiki_path.read_text(encoding="utf-8")
        _validate_wiki_shape(wiki_label, text, errors)
        source_section = _source_section(wiki_label, text, errors)
        if source_section is None:
            continue

        links = tuple(SOURCE_LINK_RE.finditer(source_section))
        if not links:
            errors.append(f"{wiki_label}: Sources section has no links")
            continue

        for match in links:
            target_text = _clean_link_target(match.group("target"))
            if not target_text.startswith("Sources/"):
                errors.append(
                    f"{wiki_label}: Sources link must point inside its context's Sources: "
                    f"{target_text}"
                )
                continue
            source_link_count += 1
            source_path = (context_root / target_text).resolve()
            if not _is_within(source_path, sources_root):
                errors.append(
                    f"{wiki_label}: source link escapes its context's Sources: {target_text}"
                )
                continue
            relative_source = source_path.relative_to(sources_root.resolve())
            if not relative_source.parts or relative_source.parts[0] != wiki_path.stem:
                errors.append(
                    f"{wiki_label}: source must be owned by Sources/{wiki_path.stem}: "
                    f"{target_text}"
                )
            if not source_path.is_file():
                errors.append(f"{wiki_label}: missing source file: {target_text}")
                continue
            referenced_sources.add(source_path)

    inbox_sources = _source_files(inbox)
    source_roots = tuple(
        context_root / "Sources"
        for context_root in context_roots
        if (context_root / "Sources").is_dir()
    )
    library_sources = tuple(
        path
        for sources_root in source_roots
        for path in _source_files(sources_root)
        if not _is_within(path, inbox)
    )
    for source_path in library_sources:
        if source_path.resolve() not in referenced_sources:
            errors.append(
                "source is not linked by its wiki: "
                f"{source_path.relative_to(vault)}"
            )
    for source_path in inbox_sources:
        warnings.append(f"unprocessed Inbox source: {source_path.relative_to(vault)}")

    if not wiki_entries:
        errors.append("no wiki Markdown files found in vault")

    return ValidationReport(
        errors=tuple(errors),
        warnings=tuple(warnings),
        wiki_count=len(wiki_entries),
        source_count=len(library_sources),
        source_link_count=source_link_count,
        inbox_count=len(inbox_sources),
    )


def _context_roots(vault: Path) -> tuple[Path, ...]:
    if not vault.is_dir():
        return ()
    contexts = [vault]
    for path in sorted(vault.iterdir()):
        if (
            path.is_dir()
            and not path.is_symlink()
            and not path.name.startswith(".")
            and path.name.casefold() not in RESERVED_CONTEXT_NAMES
        ):
            contexts.append(path)
    return tuple(contexts)


def _validate_wiki_shape(path: str, text: str, errors: list[str]) -> None:
    first_content = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not first_content.startswith("# "):
        errors.append(f"{path}: wiki must start with one level-one title")
    if sum(1 for line in text.splitlines() if line.startswith("# ")) != 1:
        errors.append(f"{path}: wiki must contain exactly one level-one title")


def _source_section(path: str, text: str, errors: list[str]) -> str | None:
    lines = text.rstrip().splitlines()
    headings = [index for index, line in enumerate(lines) if line.strip() == "## Sources"]
    if len(headings) != 1:
        errors.append(f"{path}: wiki must contain exactly one ## Sources section")
        return None
    start = headings[0]
    if any(line.startswith("## ") for line in lines[start + 1 :]):
        errors.append(f"{path}: ## Sources must be the final level-two section")
    return "\n".join(lines[start + 1 :]).strip()


def _source_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        files.append(path)
    return tuple(files)


def _clean_link_target(target: str) -> str:
    value = target.strip().strip("<>")
    value = value.split("#", 1)[0].split("?", 1)[0]
    return unquote(value)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="MEMEX repository root",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_repo(args.repo_root)
    for warning in report.warnings:
        print(f"warning: {warning}")
    for error in report.errors:
        print(f"error: {error}")
    if not report.ok:
        print(f"wiki validation failed: {len(report.errors)} error(s)")
        return 1
    print(
        "wiki validation OK: "
        f"{report.wiki_count} wiki(s), "
        f"{report.source_count} source(s), "
        f"{report.source_link_count} source link(s), "
        f"{report.inbox_count} Inbox file(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
