# AGENTS.md - MEMEX V2 Project Guide

MEMEX is being rebuilt as a fresh single-git project. This file is the stable
operating contract for agents working in this repo. Use
`docs/wiki-v2-plan.md` as the living roadmap and update it when product or
architecture direction changes.

The old project was moved intact to:

```text
/home/jack/MEMEX-legacy-2026-06-22/
```

Treat that folder as borrow-only reference material. Do not patch or revive
legacy V1 code unless the user explicitly asks for work inside the legacy
folder.

## Product Goal

MEMEX is a Wiki LLM. It turns source material into persistent markdown wikis
instead of doing classic RAG at question time.

The core loop is:

```text
source -> extracted facts -> source-to-wiki assignment -> per-wiki fact review
-> accepted fact delta -> markdown wiki build
```

The wiki is the product. Sources, ledgers, manifests, provider calls, and the
dashboard exist to keep the markdown wikis accurate, inspectable, and
source-grounded.

## Development Bias

This project is in active development. Clean iteration matters more than
preserving legacy behavior.

For implementation work, inspect the relevant subsystem first and decide whether
the right move is delete, simplify, replace, refactor, or patch. Prefer the
option that leaves the codebase smaller, clearer, and easier to maintain.

Backward compatibility is not required unless explicitly requested. Avoid
compatibility branches, stale fallbacks, and preserving old paths just in case.

## V2 Architecture Rules

Use:

- manual source-to-wiki assignment bubbles
- one central ledger for assignments, fact decisions, and build baselines
- preserved source originals in `data/source-assets/`
- SourceRecords in `data/sources/` that contain extracted facts, not asset or
  wiki lifecycle metadata
- derived `needs_review` from missing or stale fact decisions
- derived `needs_build` from accepted facts and the latest successful build
  baseline
- wiki description scope as part of review/build fingerprints
- LLM review to decide fact relevance for assigned or changed sources
- incremental wiki builds from accepted fact deltas plus existing markdown

Avoid:

- domains, categories, sensitivity tags, privacy routing, auto-populate, or word
  matching for wiki routing
- wiki assignment or review state duplicated into source manifests
- stored lifecycle flags when they can be derived
- build baselines that update before a successful markdown write
- whole-page rewrites that discard human-written markdown
- compatibility branches for V1 behavior

Wiki description changes are scope changes. They make old fact decisions stale
by derivation and should block builds until review is current for the new scope.

## Layout

```text
/home/jack/MEMEX/
  AGENTS.md
  docs/
    wiki-v2-plan.md
  app/
  data/
    source-assets/
    sources/
    wiki-ledger.json
    wiki-registry.json
  vault/
  tests/
  scripts/
```

Responsibilities:

- `app/` contains implementation logic, UI/API code, orchestration, adapters,
  and domain modules.
- `data/` contains local state, ledgers, source records, preserved source
  originals/manifests, and runtime artifacts that are not markdown wiki pages.
- `vault/` contains markdown wiki output.
- `tests/` contains automated validation.
- `scripts/` contains developer utilities and one-off maintenance helpers.
- `docs/` contains active design notes and handoff documents.

Keep source extraction, source asset storage, wiki state, markdown output, UI,
validation, and LLM orchestration as separate responsibilities. If a module
starts mixing those concerns, split it before adding more behavior.

## Current Operations

- Run the dashboard with `uv run python scripts/wiki_server.py`. Use the
  canonical dashboard port (`127.0.0.1:8765`) for local and production-like
  validation. Do not start dashboard servers on alternate ports; if the port or
  process state is stale, rerun the start script so it kills existing MEMEX
  dashboard processes and restarts the canonical port.
- Validate persisted V2 state with `uv run python scripts/wiki_validate.py`.
- Run tests with `uv run pytest` or targeted `uv run pytest tests/<file>.py`.
- Create a wiki from the dashboard with name and description scope; the
  dashboard derives the stable wiki id and Obsidian markdown file path from the
  name.
- Use `uv run python scripts/wiki_dev.py add-wiki <wiki_id> <title> <path>` for
  scripted wiki creation.

The dashboard currently supports source ingest, assignment, review, repair,
re-extraction, wiki descriptions, builds, source deletion, and provider balance
visibility. Wiki deletion/rename/split/merge remain development/configuration
operations until those workflows need dashboard UI.

## Tooling

Prefer `uv` for Python dependency management, virtual environments, locking,
and command execution whenever possible.

- Add runtime dependencies with `uv add`.
- Add development tools with `uv add --dev`.
- Use `uv sync --locked --dev` when recreating the project environment from the
  lockfile.
- Avoid ad hoc `pip` or system-interpreter installs unless `uv` cannot handle
  the task.

When touching external libraries, frameworks, APIs, MCP servers, package
configuration, or tooling, retrieve current version-specific docs first and use
documented modern APIs.

## Current Plan

Use `/home/jack/MEMEX/docs/wiki-v2-plan.md` for current priorities. The plan is
future-focused; keep completed implementation detail out of it unless it changes
an architectural rule or operating baseline.
