FROM ghcr.io/astral-sh/uv:0.10.7 AS uv

FROM python:3.13-slim-bookworm

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY memex_mcp ./memex_mcp

RUN useradd --create-home --uid 10001 memex
USER memex

EXPOSE 9020

CMD ["/app/.venv/bin/python", "-m", "memex_mcp.server"]
