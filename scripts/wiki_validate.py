#!/usr/bin/env python3
"""Validate the filesystem-only MEMEX source and wiki layout."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

SOURCE_LINK_RE = re.compile(r"\[[^\]]*\]\((?P<target><[^>\n]+>|[^)\n]+)\)")


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
    return validate_vault(Path(repo_root) / "vault")


def validate_vault(vault_root: str | Path) -> ValidationReport:
    vault = Path(vault_root).resolve()
    sources_root = vault / "Sources"
    inbox = sources_root / "Inbox"
    errors: list[str] = []
    warnings: list[str] = []

    # Never read through vault symlinks, including directory and broken links.
    for directory, folders, files in os.walk(vault, followlinks=False):
        for name in sorted(folders + files):
            path = Path(directory) / name
            if path.is_symlink():
                errors.append(f"symlink is not allowed in vault: {path.relative_to(vault)}")
    if errors:
        return ValidationReport(tuple(errors), (), 0, 0, 0, 0)

    if not vault.is_dir():
        errors.append("missing vault directory")
    if not sources_root.is_dir():
        errors.append("missing vault/Sources directory")
    if not inbox.is_dir():
        errors.append("missing vault/Sources/Inbox directory")

    root_markdown = sorted(vault.glob("*.md")) if vault.is_dir() else []
    wiki_paths = [path for path in root_markdown if (sources_root / path.stem).is_dir()]
    non_wiki_paths = [path for path in root_markdown if path not in wiki_paths]
    for path in sorted(vault.rglob("*.md")):
        relative = path.relative_to(vault)
        if len(relative.parts) < 2 or relative.parts[0] in {"Sources", "Temp"}:
            continue
        if "<!-- memex:wiki -->" in path.read_text(encoding="utf-8").splitlines():
            wiki_paths.append(path)
    referenced_sources: set[Path] = set()
    source_link_count = 0

    for note_path in non_wiki_paths:
        warnings.append(
            f"root Markdown is not a MEMEX wiki because it has no matching source folder: "
            f"{note_path.relative_to(vault)}"
        )

    for wiki_path in wiki_paths:
        relative_wiki = wiki_path.relative_to(vault)
        owner = wiki_path.stem if len(relative_wiki.parts) == 1 else relative_wiki.parts[0]
        text = wiki_path.read_text(encoding="utf-8")
        if len(relative_wiki.parts) > 1:
            content = [line.strip() for line in text.splitlines() if line.strip()]
            if content[1:2] != ["<!-- memex:wiki -->"]:
                errors.append(f"{relative_wiki}: wiki marker must follow the title")
        _validate_wiki_shape(relative_wiki, text, errors)
        source_section = _source_section(relative_wiki, text, errors)
        if source_section is None:
            continue

        links = tuple(SOURCE_LINK_RE.finditer(source_section))
        if not links:
            errors.append(f"{wiki_path.name}: Sources section has no links")
            continue

        for match in links:
            target_text = _clean_link_target(match.group("target"))
            if Path(target_text).is_absolute():
                errors.append(f"{relative_wiki}: source link must be relative: {target_text}")
                continue
            source_path = (wiki_path.parent / target_text).resolve()
            if not _is_within(source_path, sources_root):
                errors.append(
                    f"{relative_wiki}: source link escapes vault/Sources: "
                    f"{target_text}"
                )
                continue
            source_link_count += 1
            relative_source = source_path.relative_to(sources_root.resolve())
            if not relative_source.parts or relative_source.parts[0] != owner:
                errors.append(
                    f"{relative_wiki}: source must be owned by Sources/{owner}: "
                    f"{target_text}"
                )
                continue
            if not source_path.is_file():
                errors.append(f"{wiki_path.name}: missing source file: {target_text}")
                continue
            referenced_sources.add(source_path)

    inbox_sources = _source_files(inbox)
    library_sources = tuple(
        path for path in _source_files(sources_root) if not _is_within(path, inbox)
    )
    for source_path in library_sources:
        if source_path.resolve() not in referenced_sources:
            errors.append(
                "source outside Inbox is not linked by its wiki: "
                f"{source_path.relative_to(vault)}"
            )
    for source_path in inbox_sources:
        warnings.append(f"unprocessed Inbox source: {source_path.relative_to(vault)}")

    if not wiki_paths:
        errors.append("no wiki Markdown files found in vault")

    return ValidationReport(
        errors=tuple(errors),
        warnings=tuple(warnings),
        wiki_count=len(wiki_paths),
        source_count=len(library_sources),
        source_link_count=source_link_count,
        inbox_count=len(inbox_sources),
    )


def _validate_wiki_shape(path: Path, text: str, errors: list[str]) -> None:
    first_content = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not first_content.startswith("# "):
        errors.append(f"{path.name}: wiki must start with one level-one title")
    if sum(1 for line in text.splitlines() if line.startswith("# ")) != 1:
        errors.append(f"{path.name}: wiki must contain exactly one level-one title")


def _source_section(path: Path, text: str, errors: list[str]) -> str | None:
    lines = text.rstrip().splitlines()
    headings = [index for index, line in enumerate(lines) if line.strip() == "## Sources"]
    if len(headings) != 1:
        errors.append(f"{path.name}: wiki must contain exactly one ## Sources section")
        return None
    start = headings[0]
    if any(line.startswith("## ") for line in lines[start + 1 :]):
        errors.append(f"{path.name}: ## Sources must be the final level-two section")
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
    roots = parser.add_mutually_exclusive_group()
    roots.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="MEMEX repository root",
    )
    roots.add_argument("--vault-root", type=Path, help="Independent vault directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_vault(args.vault_root) if args.vault_root else validate_repo(args.repo_root)
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
