from pathlib import Path

import pytest
from scripts.wiki_validate import main, validate_repo


@pytest.mark.parametrize("kind", ["source-file", "source-dir", "sources-root", "wiki"])
def test_symlinks_are_rejected(tmp_path: Path, kind: str) -> None:
    root = _valid_repo(tmp_path)
    vault = root / "vault"
    target = {
        "source-file": vault / "Sources/home-lab/hardware.md",
        "source-dir": vault / "Sources/home-lab",
        "sources-root": vault / "Sources",
        "wiki": vault / "home-lab.md",
    }[kind]
    original = root / "outside"
    target.rename(original)
    target.symlink_to(original, target_is_directory=original.is_dir())
    report = validate_repo(root)
    assert not report.ok
    assert any("symlink" in error for error in report.errors)


def test_external_vault_cli(tmp_path: Path, capsys) -> None:
    root = _valid_repo(tmp_path)
    assert main(["--vault-root", str(root / "vault")]) == 0
    assert "1 wiki(s)" in capsys.readouterr().out
    assert main(["--repo-root", str(root)]) == 0


def _valid_repo(tmp_path: Path) -> Path:
    source_dir = tmp_path / "vault" / "Sources" / "home-lab"
    inbox = tmp_path / "vault" / "Sources" / "Inbox"
    source_dir.mkdir(parents=True)
    inbox.mkdir()
    (source_dir / "hardware.md").write_text("# Hardware\n", encoding="utf-8")
    (tmp_path / "vault" / "home-lab.md").write_text(
        "# Home Lab\n\nServer details.\n\n"
        "## Sources\n\n"
        "- [Hardware](Sources/home-lab/hardware.md)\n",
        encoding="utf-8",
    )
    return tmp_path


def _domain_repo(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "Sources" / "Inbox").mkdir(parents=True)
    (vault / "Sources" / "Clinical" / "Epic").mkdir(parents=True)
    (vault / "Sources" / "Clinical" / "Epic" / "guide.pdf").write_bytes(b"original")
    for name in ("Clinical/Epic/Orders.md", "Clinical/Training.md"):
        path = vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        prefix = "../" * (len(Path(name).parts) - 1)
        path.write_text(
            "# Guide\n<!-- memex:wiki -->\n\n## Sources\n"
            f"- [Guide]({prefix}Sources/Clinical/Epic/guide.pdf#page=3)\n"
        )
    (vault / "Clinical" / "index.md").write_text("# Navigation\n")
    (vault / "Temp").mkdir()
    (vault / "Temp/scratch.md").write_text("# Scratch\n<!-- memex:wiki -->\n")
    return tmp_path


def test_nested_wikis_share_domain_sources(tmp_path: Path) -> None:
    report = validate_repo(_domain_repo(tmp_path))
    assert report.ok, report.errors
    assert report.wiki_count == 2
    assert report.source_count == 1
    assert report.source_link_count == 2
    assert report.warnings == ()


def test_source_links_must_be_relative(tmp_path: Path) -> None:
    root = _valid_repo(tmp_path)
    wiki = root / "vault/home-lab.md"
    wiki.write_text(wiki.read_text().replace("Sources/home-lab/hardware.md",
                                           str(root / "vault/Sources/home-lab/hardware.md")))
    report = validate_repo(root)
    assert not report.ok
    assert any("relative" in error for error in report.errors)


@pytest.mark.parametrize("target", [
    "Sources/home-lab/Guide%20%28v1%29%23draft.pdf#page=7",
    "<Sources/home-lab/Guide (v1)%23draft.pdf#page=7>",
])
def test_encoded_source_names(tmp_path: Path, target: str) -> None:
    root = _valid_repo(tmp_path)
    (root / "vault/Sources/home-lab/hardware.md").rename(
        root / "vault/Sources/home-lab/Guide (v1)#draft.pdf"
    )
    (root / "vault/home-lab.md").write_text(f"# Guide\n\n## Sources\n- [Guide]({target})\n")
    report = validate_repo(root)
    assert report.ok, report.errors


def test_nested_marker_must_follow_title(tmp_path: Path) -> None:
    root = _domain_repo(tmp_path)
    path = root / "vault/Clinical/Training.md"
    path.write_text(path.read_text().replace("# Guide\n<!-- memex:wiki -->",
                                            "# Guide\nBody\n<!-- memex:wiki -->"))
    report = validate_repo(root)
    assert not report.ok
    assert any("marker" in error for error in report.errors)


@pytest.mark.parametrize("target, message", [
    ("../../Sources/Other/other.pdf", "must be owned by Sources/Clinical"),
    ("../../Sources/Inbox/new.pdf", "must be owned by Sources/Clinical"),
    ("../../Sources/Clinical/missing.pdf", "missing source file"),
    ("../../Sources/Clinical/../../../outside.pdf", "escapes vault/Sources"),
    ("../../Sources/Clinical/%2e%2e/%2e%2e/%2e%2e/outside.pdf", "escapes vault/Sources"),
    ("https://example.com/guide.pdf", "escapes vault/Sources"),
])
def test_nested_source_boundaries(tmp_path: Path, target: str, message: str) -> None:
    root = _domain_repo(tmp_path)
    (root / "vault/Clinical/Epic/Orders.md").write_text(
        f"# Orders\n<!-- memex:wiki -->\n\n## Sources\n- [Source]({target})\n"
    )
    report = validate_repo(root)
    assert not report.ok
    assert any(message in error for error in report.errors)


@pytest.mark.parametrize("body, message", [
    ("# Wiki\n<!-- memex:wiki -->\n", "exactly one ## Sources"),
    ("# Wiki\n<!-- memex:wiki -->\n## Sources\n", "has no links"),
    ("# Wiki\n<!-- memex:wiki -->\n## Sources\n## Sources\n", "exactly one ## Sources"),
    ("<!-- memex:wiki -->\n## Sources\n", "must start"),
])
def test_nested_source_sections(tmp_path: Path, body: str, message: str) -> None:
    root = _domain_repo(tmp_path)
    (root / "vault/Clinical/Epic/Orders.md").write_text(body)
    report = validate_repo(root)
    assert not report.ok
    assert any(message in error for error in report.errors)


def test_source_markdown_is_not_a_wiki(tmp_path: Path) -> None:
    root = _domain_repo(tmp_path)
    source = root / "vault/Sources/Clinical/excerpt.md"
    source.write_text("# Original\n<!-- memex:wiki -->\n")
    wiki = root / "vault/Clinical/Training.md"
    wiki.write_text(wiki.read_text() + "- [Excerpt](../Sources/Clinical/excerpt.md)\n")
    report = validate_repo(root)
    assert report.ok, report.errors
    assert report.wiki_count == 2
    assert report.source_count == 2


def test_valid_repo_passes(tmp_path: Path) -> None:
    report = validate_repo(_valid_repo(tmp_path))

    assert report.ok
    assert report.errors == ()
    assert report.wiki_count == 1
    assert report.source_count == 1
    assert report.source_link_count == 1


def test_broken_source_link_fails(tmp_path: Path) -> None:
    root = _valid_repo(tmp_path)
    (root / "vault" / "home-lab.md").write_text(
        "# Home Lab\n\n## Sources\n\n"
        "- [Missing](Sources/home-lab/missing.md)\n",
        encoding="utf-8",
    )

    report = validate_repo(root)

    assert not report.ok
    assert any("missing source file" in error for error in report.errors)
    assert any("not linked by its wiki" in error for error in report.errors)


def test_source_must_be_in_owning_wiki_folder(tmp_path: Path) -> None:
    root = _valid_repo(tmp_path)
    other_dir = root / "vault" / "Sources" / "other-wiki"
    other_dir.mkdir()
    (other_dir / "other.md").write_text("other", encoding="utf-8")
    (root / "vault" / "home-lab.md").write_text(
        "# Home Lab\n\n## Sources\n\n"
        "- [Other](Sources/other-wiki/other.md)\n",
        encoding="utf-8",
    )

    report = validate_repo(root)

    assert not report.ok
    assert any("must be owned by Sources/home-lab" in error for error in report.errors)


def test_inbox_file_warns_without_failing(tmp_path: Path) -> None:
    root = _valid_repo(tmp_path)
    (root / "vault" / "Sources" / "Inbox" / "new-notes.txt").write_text(
        "new notes",
        encoding="utf-8",
    )

    report = validate_repo(root)

    assert report.ok
    assert report.inbox_count == 1
    assert report.warnings == ("unprocessed Inbox source: Sources/Inbox/new-notes.txt",)


def test_unrelated_root_markdown_is_not_validated_as_a_wiki(tmp_path: Path) -> None:
    root = _valid_repo(tmp_path)
    (root / "vault" / "phone-sync-check.md").write_text(
        "# Phone sync check\n",
        encoding="utf-8",
    )

    report = validate_repo(root)

    assert report.ok
    assert report.wiki_count == 1
    assert report.warnings == (
        "root Markdown is not a MEMEX wiki because it has no matching source folder: "
        "phone-sync-check.md",
    )


def test_sources_must_be_the_final_section(tmp_path: Path) -> None:
    root = _valid_repo(tmp_path)
    wiki = root / "vault" / "home-lab.md"
    wiki.write_text(
        wiki.read_text(encoding="utf-8") + "\n## Later section\n",
        encoding="utf-8",
    )

    report = validate_repo(root)

    assert not report.ok
    assert any("Sources must be the final" in error for error in report.errors)
