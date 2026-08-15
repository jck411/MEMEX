#!/usr/bin/env python3
"""Validate the filesystem-only MEMEX source and wiki layout."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

SOURCE_LINK_RE = re.compile(r"\[[^\]]*\]\((?P<target>[^)]+)\)")
MANAGED_MARKERS = (
    "<!-- MEMEX:SYNTHESIS:",
    "<!-- MEMEX:FACTS:",
    "<!-- MEMEX:REFERENCES:",
)
LEGACY_PATHS = (
    "data/source-assets",
    "data/sources",
    "data/wiki-ledger.json",
    "data/wiki-registry.json",
)


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
    sources_root = vault / "Sources"
    inbox = sources_root / "Inbox"
    errors: list[str] = []
    warnings: list[str] = []

    for relative_path in LEGACY_PATHS:
        if (root / relative_path).exists():
            errors.append(f"legacy MEMEX state still exists: {relative_path}")

    if not vault.is_dir():
        errors.append("missing vault directory")
    if not sources_root.is_dir():
        errors.append("missing vault/Sources directory")
    if not inbox.is_dir():
        errors.append("missing vault/Sources/Inbox directory")

    wiki_paths = sorted(vault.glob("*.md")) if vault.is_dir() else []
    referenced_sources: set[Path] = set()
    source_link_count = 0

    for wiki_path in wiki_paths:
        text = wiki_path.read_text(encoding="utf-8")
        _validate_wiki_shape(wiki_path, text, errors)
        source_section = _source_section(wiki_path, text, errors)
        if source_section is None:
            continue

        links = tuple(SOURCE_LINK_RE.finditer(source_section))
        if not links:
            errors.append(f"{wiki_path.name}: Sources section has no links")
            continue

        for match in links:
            target_text = _clean_link_target(match.group("target"))
            if not target_text.startswith("Sources/"):
                errors.append(
                    f"{wiki_path.name}: Sources link must point inside vault/Sources: "
                    f"{target_text}"
                )
                continue
            source_link_count += 1
            source_path = (vault / target_text).resolve()
            if not _is_within(source_path, sources_root):
                errors.append(f"{wiki_path.name}: source link escapes vault/Sources: {target_text}")
                continue
            relative_source = source_path.relative_to(sources_root.resolve())
            if not relative_source.parts or relative_source.parts[0] != wiki_path.stem:
                errors.append(
                    f"{wiki_path.name}: source must be owned by Sources/{wiki_path.stem}: "
                    f"{target_text}"
                )
            if not source_path.is_file():
                errors.append(f"{wiki_path.name}: missing source file: {target_text}")
                continue
            referenced_sources.add(source_path)

    library_sources = _source_files(sources_root, include_inbox=False)
    inbox_sources = _source_files(inbox, include_inbox=True)
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
    for marker in MANAGED_MARKERS:
        if marker in text:
            errors.append(f"{path.name}: obsolete managed marker remains: {marker}")


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


def _source_files(root: Path, *, include_inbox: bool) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if not include_inbox and "Inbox" in path.relative_to(root).parts:
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
