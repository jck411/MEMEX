from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
import pytest
from memex_mcp import server
from memex_mcp.vault import Vault


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    (tmp_path / "wiki.md").write_text("# Wiki\n\nServer details\n", encoding="utf-8")
    (tmp_path / "Notes" / "Inbox").mkdir(parents=True)
    (tmp_path / "Notes" / "Inbox" / "phone.md").write_text(
        "# Phone\n\nRemember the blue cable\n", encoding="utf-8"
    )
    (tmp_path / "Sources").mkdir()
    (tmp_path / "Sources" / "source.md").write_text(
        "# Source\n\nBlue source material\n", encoding="utf-8"
    )
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "plugin.md").write_text("hidden", encoding="utf-8")
    (tmp_path / "redflag.md").write_text("control", encoding="utf-8")
    return tmp_path


def test_list_includes_wikis_notes_and_sources(vault_root: Path) -> None:
    result = Vault(vault_root).list_markdown()

    assert [item["path"] for item in result["files"]] == [
        "Notes/Inbox/phone.md",
        "Sources/source.md",
        "wiki.md",
    ]
    assert result["total"] == 3
    assert not result["truncated"]


def test_list_filters_by_directory(vault_root: Path) -> None:
    result = Vault(vault_root).list_markdown(path_prefix="Notes")

    assert [item["path"] for item in result["files"]] == ["Notes/Inbox/phone.md"]


def test_read_is_line_addressable(vault_root: Path) -> None:
    result = Vault(vault_root).read_markdown("Notes/Inbox/phone.md", start_line=2, max_lines=2)

    assert result["content"] == "\nRemember the blue cable"
    assert result["start_line"] == 2
    assert result["end_line"] == 3
    assert result["total_lines"] == 3


@pytest.mark.parametrize(
    "path",
    ["../outside.md", "/etc/passwd.md", ".obsidian/plugin.md", "redflag.md", "wiki.txt"],
)
def test_read_rejects_unsafe_or_non_content_paths(vault_root: Path, path: str) -> None:
    with pytest.raises((ValueError, FileNotFoundError)):
        Vault(vault_root).read_markdown(path)


def test_symlink_cannot_escape_vault(vault_root: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    os.symlink(outside, vault_root / "linked.md")

    assert "linked.md" not in {
        item["path"] for item in Vault(vault_root).list_markdown()["files"]
    }
    with pytest.raises(ValueError, match="escapes"):
        Vault(vault_root).read_markdown("linked.md")


def test_search_covers_phone_notes_and_sources(vault_root: Path) -> None:
    result = Vault(vault_root).search_markdown("BLUE")

    assert [(item["path"], item["line"]) for item in result["matches"]] == [
        ("Notes/Inbox/phone.md", 3),
        ("Sources/source.md", 3),
    ]


def test_status_excludes_control_markdown(vault_root: Path) -> None:
    result = Vault(vault_root).status()

    assert result["status"] == "ok"
    assert result["markdown_count"] == 3


def test_http_endpoint_requires_token_and_allows_configured_origin(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server, "vault", Vault(vault_root))
    app = server.create_app("test-token", {"https://allowed.example"})
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }

    async def exercise_app() -> None:
        transport = httpx.ASGITransport(app=app)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                assert (await client.get("/health")).json()["markdown_count"] == 3
                assert (await client.post("/mcp", json=initialize)).status_code == 401
                blocked = await client.post(
                    "/mcp",
                    json=initialize,
                    headers={
                        "Authorization": "Bearer test-token",
                        "Origin": "https://blocked.example",
                    },
                )
                assert blocked.status_code == 403
                response = await client.post(
                    "/mcp",
                    json=initialize,
                    headers={
                        "Authorization": "Bearer test-token",
                        "Origin": "https://allowed.example",
                        "Accept": "application/json, text/event-stream",
                    },
                )
                assert response.status_code == 200
                assert "Obsidian Vault" in response.text

    asyncio.run(exercise_app())
