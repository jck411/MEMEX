"""Streamable HTTP MCP server for read-only Obsidian vault access."""

from __future__ import annotations

import hmac
import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import uvicorn
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .vault import Vault

REPO_ROOT = Path(__file__).resolve().parents[1]
vault = Vault(os.environ.get("MEMEX_VAULT_ROOT", REPO_ROOT / "vault"))
mcp = FastMCP("Obsidian Vault")


@mcp.tool
def vault_list_markdown(path_prefix: str = "", limit: int = 100) -> dict[str, Any]:
    """List user Markdown anywhere in the Obsidian vault."""
    return vault.list_markdown(path_prefix=path_prefix, limit=limit)


@mcp.tool
def vault_read_markdown(
    path: str,
    start_line: int = 1,
    max_lines: int = 400,
) -> dict[str, Any]:
    """Read a vault-relative Markdown file, optionally in bounded line chunks."""
    return vault.read_markdown(path=path, start_line=start_line, max_lines=max_lines)


@mcp.tool
def vault_search_markdown(
    query: str,
    path_prefix: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Search all user Markdown with a case-insensitive literal query."""
    return vault.search_markdown(query=query, path_prefix=path_prefix, limit=limit)


@mcp.tool
def vault_recent_markdown(limit: int = 20) -> dict[str, Any]:
    """List the most recently modified Markdown files in the vault."""
    return vault.recent_markdown(limit=limit)


@mcp.tool
def vault_status() -> dict[str, Any]:
    """Report whether the synchronized vault is readable and how many notes it contains."""
    return vault.status()


class BearerOriginGuard:
    """Require one opaque bearer token and reject unexpected browser origins."""

    def __init__(self, app: Callable[..., Awaitable[None]], token: str, origins: set[str]) -> None:
        self.app = app
        self.token = token.encode()
        self.origins = origins

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[dict[str, Any]]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        origin = headers.get(b"origin", b"").decode()
        if origin and origin not in self.origins:
            await self._reject(send, 403, "origin is not allowed")
            return
        authorization = headers.get(b"authorization", b"")
        expected = b"Bearer " + self.token
        if not hmac.compare_digest(authorization, expected):
            await self._reject(send, 401, "valid bearer authentication is required")
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(
        send: Callable[..., Awaitable[None]], status: int, message: str
    ) -> None:
        body = json.dumps({"error": message}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


async def health(_: Request) -> JSONResponse:
    """Return process and vault health without exposing note content."""
    status = vault.status()
    code = 200 if status["status"] == "ok" else 503
    return JSONResponse(status, status_code=code)


def create_app(token: str, allowed_origins: set[str] | None = None) -> Starlette:
    """Build the authenticated HTTP application."""
    if not token:
        raise ValueError("MEMEX_MCP_BEARER_TOKEN must not be empty")
    mcp_app = mcp.http_app(path="/mcp", stateless_http=True)
    guarded = BearerOriginGuard(mcp_app, token, allowed_origins or set())
    return Starlette(
        routes=[Route("/health", health), Mount("/", app=guarded)],
        lifespan=mcp_app.lifespan,
    )


def main() -> None:
    """Run the MCP endpoint using environment-provided secrets and network settings."""
    token = os.environ.get("MEMEX_MCP_BEARER_TOKEN", "")
    origins = {
        value.strip()
        for value in os.environ.get("MEMEX_MCP_ALLOWED_ORIGINS", "").split(",")
        if value.strip()
    }
    app = create_app(token=token, allowed_origins=origins)
    uvicorn.run(
        app,
        host=os.environ.get("MEMEX_MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("MEMEX_MCP_PORT", "9020")),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("MEMEX_MCP_FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


if __name__ == "__main__":
    main()
