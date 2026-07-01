# MEMEX

MEMEX is a personal Wiki LLM. It turns source material into persistent markdown
wikis.

Current status: usable local app. The main development phase is source recovery
and wiki construction: put recovered old source material in
`/home/jack/MEMEX/data/source-drafts/`, extract useful drafts into source
records, assign sources to wikis, review facts, and build markdown pages.

## Repository Layout

- `app/` contains implementation code for domain logic, storage, LLM
  orchestration, routes, and rendering.
- `scripts/` contains developer utilities and maintenance helpers.
- `tests/` contains automated validation.
- `docs/wiki-plan.md` is the living development plan.
- `data/` contains private local source drafts, source assets, source records,
  ledgers, registries, and runtime scratch files.
- `vault/` contains generated markdown wiki output.

Runtime state under `data/` and generated markdown under `vault/` are ignored by
Git by default because they may contain private information.

## Source Recovery

Use `data/source-drafts/` for recovered old source text before extraction. The
normal path is:

1. Prepare a source draft or upload a source file.
2. Extract it into a SourceRecord under `data/sources/`.
3. Preserve the original material under `data/source-assets/`.
4. Assign the source to one or more wikis.
5. Review facts for each wiki.
6. Build markdown pages in `vault/`.

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
