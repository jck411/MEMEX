# MEMEX

MEMEX is a personal Wiki LLM. It turns source material into persistent markdown
wikis.

Current status: usable local app. The main development phase is source recovery
and wiki construction: ingest source material into preserved assets and source
records, assign sources to wikis, review facts, and build markdown pages.

## Repository Layout

- `app/` contains implementation code for domain logic, storage, LLM
  orchestration, routes, and rendering.
- `scripts/` contains developer utilities and maintenance helpers.
- `tests/` contains automated validation.
- `docs/wiki-plan.md` is the living development plan.
- `data/` contains private local source assets, source records,
  ledgers, registries, and runtime scratch files.
- `vault/` contains generated markdown wiki output.

Runtime state under `data/` and generated markdown under `vault/` are ignored by
Git by default because they may contain private information.

## Source Ingestion

MEMEX has no draft or staging state. Material becomes a source only through
ingestion, which preserves the original under `data/source-assets/` and writes
its SourceRecord under `data/sources/`. The normal path is:

1. Ingest supplied or recovered source material directly.
2. Assign the source to one or more wikis.
3. Review facts for each wiki.
4. Build markdown pages in `vault/`.

## Commands

Run the dashboard:

```bash
uv run python scripts/wiki_server.py
```

Validate local state:

```bash
uv run python scripts/wiki_validate.py
```

Run tests:

```bash
uv run pytest
```

Inspect CLI utilities:

```bash
uv run python scripts/wiki_dev.py --help
uv run python scripts/wiki_extract.py --help
```

## Project Docs

- [docs/wiki-plan.md](docs/wiki-plan.md) tracks current priorities.
- [AGENTS.md](AGENTS.md) is the operating contract for coding agents.
