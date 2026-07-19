# MEMEX Agent Guide

MEMEX turns source material into persistent, source-grounded markdown wikis:

```text
source -> extracted facts -> source-to-wiki assignment -> per-wiki fact review
-> accepted fact delta -> markdown wiki build
```

The wiki is the product. Sources, ledgers, provider calls, and the dashboard
exist to keep it accurate and inspectable. Use `docs/wiki-plan.md` for current
priorities and update it when product or architecture direction changes.

## Development

This project favors clean iteration over legacy compatibility. Before editing,
inspect the relevant subsystem and choose deletion, simplification, replacement,
refactoring, or patching based on which leaves the codebase clearest. Remove
obsolete paths rather than preserving them just in case.

Keep source extraction, source assets, wiki state, markdown output, UI,
validation, and LLM orchestration as separate responsibilities.

## Architecture

Use:

- manual source-to-wiki assignment
- one central ledger for assignments, fact decisions, and build baselines
- preserved source originals in `data/source-assets/`
- fact-only SourceRecords in `data/sources/`
- derived `needs_review` from missing or stale fact decisions
- derived `needs_build` from accepted facts and the last successful baseline
- wiki description scope in review and build fingerprints
- LLM relevance review for assigned or changed sources
- incremental builds from accepted fact deltas and existing markdown

Avoid:

- automatic, tag-based, or word-matching wiki routing
- wiki assignment or review state in source manifests
- stored lifecycle flags that can be derived
- build baseline updates before a successful markdown write
- manual edits to vault wiki markdown or `data/wiki-ledger.json`
- whole-page rewrites that discard managed markdown outside generated sections
- compatibility paths for retired workflows

Wiki description changes are scope changes. They make old fact decisions stale
and block builds until review is current for the new scope.

## Agent-Run Wiki Updates

When Jack asks to update or refresh a wiki, or names a wiki and material to
incorporate, run the complete workflow in `docs/wiki-update-runbook.md`: ingest
or extract, assign, review, build, inspect, and validate. If the wiki and source
are clear, proceed without asking Jack to operate the dashboard.

Choose the smallest grounded source operation:

- repair a minor extraction error using its preserved original
- re-extract when coverage or fact boundaries are poor
- ingest when supplied material is not grounded in an existing original
- review and build when source facts are already complete

Do not edit vault markdown or the ledger by hand. Before reporting success,
inspect the generated markdown for coverage and fidelity, then run
`uv run python scripts/wiki_validate.py`. Report the source operation,
review/build result, output path, and validation result.

Prepared source drafts are in `data/source-drafts/`.

## Commands

- Dashboard: `uv run python scripts/wiki_server.py`
- Tests: `uv run pytest` or `uv run pytest tests/<file>.py`
- Validation: `uv run python scripts/wiki_validate.py`
- Scripted wiki creation:
  `uv run python scripts/wiki_dev.py add-wiki <wiki_id> <title> <path>`

Use only the canonical dashboard address `127.0.0.1:8765`. If its process state
is stale, rerun the start script so it restarts the canonical port. Prefer `uv`
for Python dependencies, environments, and commands.
