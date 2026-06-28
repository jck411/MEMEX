"""Local HTTP server for the wiki dashboard."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from .dashboard_action_types import (
    BalanceProvider,
    SourceExtractionRunner,
    SourceFixRunner,
    SourceReviewRunner,
    WikiBuildRunner,
)
from .dashboard_routes import (
    DashboardResponse,
    handle_dashboard_get,
    handle_dashboard_post,
)
from .dashboard_runtime import DashboardRuntime
from .model_profiles import DEFAULT_EXTRACTION_PROFILE_ID
from .runtime_services import dashboard_runtime_from_env
from .workflows import WikiWorkspace

_CLIENT_DISCONNECT_ERRORS = (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)


def create_dashboard_server(
    workspace: WikiWorkspace,
    host: str = "127.0.0.1",
    port: int = 8765,
    balance_provider: BalanceProvider | None = None,
    source_extractor: SourceExtractionRunner | None = None,
    extraction_model_spec: str = DEFAULT_EXTRACTION_PROFILE_ID,
    source_fixer: SourceFixRunner | None = None,
    source_reviewer: SourceReviewRunner | None = None,
    wiki_builder: WikiBuildRunner | None = None,
) -> ThreadingHTTPServer:
    handler = create_dashboard_handler(
        workspace,
        balance_provider,
        source_extractor,
        extraction_model_spec,
        source_fixer,
        source_reviewer,
        wiki_builder,
    )
    return ThreadingHTTPServer((host, port), handler)


def run_dashboard_server(
    workspace: WikiWorkspace,
    host: str = "127.0.0.1",
    port: int = 8765,
    env_file: str | Path = ".env",
    balance_provider: BalanceProvider | None = None,
    source_extractor: SourceExtractionRunner | None = None,
    source_fixer: SourceFixRunner | None = None,
    source_reviewer: SourceReviewRunner | None = None,
    wiki_builder: WikiBuildRunner | None = None,
) -> None:
    runtime = dashboard_runtime_from_env(
        workspace,
        env_file=env_file,
        balance_provider=balance_provider,
        source_extractor=source_extractor,
        source_fixer=source_fixer,
        source_reviewer=source_reviewer,
        wiki_builder=wiki_builder,
    )
    server = ThreadingHTTPServer(
        (host, port),
        _dashboard_handler_for_runtime(runtime),
    )
    address, bound_port = server.server_address
    print(f"serving MEMEX dashboard at http://{address}:{bound_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("")
    finally:
        server.server_close()


def create_dashboard_handler(
    workspace: WikiWorkspace,
    balance_provider: BalanceProvider | None = None,
    source_extractor: SourceExtractionRunner | None = None,
    extraction_model_spec: str = DEFAULT_EXTRACTION_PROFILE_ID,
    source_fixer: SourceFixRunner | None = None,
    source_reviewer: SourceReviewRunner | None = None,
    wiki_builder: WikiBuildRunner | None = None,
) -> Callable[..., BaseHTTPRequestHandler]:
    runtime = DashboardRuntime(
        workspace=workspace,
        balance_provider=balance_provider,
        source_extractor=source_extractor,
        extraction_model_spec=extraction_model_spec,
        source_fixer=source_fixer,
        source_reviewer=source_reviewer,
        wiki_builder=wiki_builder,
    )
    return _dashboard_handler_for_runtime(runtime)


def _dashboard_handler_for_runtime(
    runtime: DashboardRuntime,
) -> Callable[..., BaseHTTPRequestHandler]:
    class DashboardRequestHandler(BaseHTTPRequestHandler):
        def handle_one_request(self) -> None:
            try:
                super().handle_one_request()
            except _CLIENT_DISCONNECT_ERRORS:
                self.close_connection = True

        def do_GET(self) -> None:
            self._send_dashboard_response(handle_dashboard_get(runtime, self.path))

        def do_POST(self) -> None:
            self._send_dashboard_response(
                handle_dashboard_post(
                    runtime,
                    self.path,
                    self.headers.get("Content-Type", ""),
                    self._read_body(),
                )
            )

        def log_message(self, format: str, *args) -> None:
            return

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", "0"))
            return self.rfile.read(length) if length else b""

        def _send_dashboard_response(self, response: DashboardResponse) -> None:
            self.send_response(response.status)
            if response.location:
                self.send_header("Location", response.location)
                self.end_headers()
                return
            payload = response.body.encode("utf-8")
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return DashboardRequestHandler
