from pathlib import Path

from scripts.wiki_validate import validate_repo


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


def _add_topic_wiki(root: Path) -> None:
    topic = root / "vault" / "health"
    source_dir = topic / "Sources" / "shoes"
    source_dir.mkdir(parents=True)
    (source_dir / "measurements.md").write_text(
        "# Foot measurements\n",
        encoding="utf-8",
    )
    (topic / "shoes.md").write_text(
        "# Shoes\n\nMy current fit information.\n\n"
        "## Sources\n\n"
        "- [Foot measurements](Sources/shoes/measurements.md)\n",
        encoding="utf-8",
    )


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


def test_ordinary_notes_do_not_participate_in_wiki_validation(tmp_path: Path) -> None:
    root = _valid_repo(tmp_path)
    (root / "vault" / "phone-sync-check.md").write_text(
        "# Phone sync check\n",
        encoding="utf-8",
    )
    topic = root / "vault" / "health"
    topic.mkdir()
    (topic / "buy-shoe-laces.md").write_text(
        "# Buy shoe laces\n",
        encoding="utf-8",
    )

    report = validate_repo(root)

    assert report.ok
    assert report.wiki_count == 1
    assert report.warnings == ()


def test_topic_folder_wiki_uses_its_own_source_library(tmp_path: Path) -> None:
    root = _valid_repo(tmp_path)
    _add_topic_wiki(root)
    (root / "vault" / "health" / "buy-shoe-laces.md").write_text(
        "# Buy shoe laces\n",
        encoding="utf-8",
    )

    report = validate_repo(root)

    assert report.ok
    assert report.errors == ()
    assert report.warnings == ()
    assert report.wiki_count == 2
    assert report.source_count == 2
    assert report.source_link_count == 2


def test_topic_wiki_cannot_link_to_general_sources(tmp_path: Path) -> None:
    root = _valid_repo(tmp_path)
    _add_topic_wiki(root)
    topic_wiki = root / "vault" / "health" / "shoes.md"
    topic_wiki.write_text(
        "# Shoes\n\n## Sources\n\n"
        "- [Hardware](../Sources/home-lab/hardware.md)\n",
        encoding="utf-8",
    )

    report = validate_repo(root)

    assert not report.ok
    assert any(
        "health/shoes.md: Sources link must point inside its context's Sources"
        in error
        for error in report.errors
    )
    assert any(
        "source is not linked by its wiki: health/Sources/shoes/measurements.md"
        in error
        for error in report.errors
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
