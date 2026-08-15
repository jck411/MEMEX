# MEMEX Agent Guide

MEMEX is a source library and a set of source-grounded Markdown wikis. Codex is
the only semantic processor: it reads sources, decides what belongs in a wiki,
and edits that wiki directly.

```text
source file -> Codex -> wiki Markdown
```

There is no dashboard, provider API, extraction database, review ledger, or
generated build state.

## Layout

- `vault/Sources/Inbox/` is the drop location for new material.
- `vault/Sources/<wiki-id>/` contains the original sources used by that wiki.
- `vault/<wiki-id>.md` is the finished wiki page.
- `docs/wiki-update-runbook.md` contains the complete update procedure.

Source folder names and wiki filenames use the same `wiki-id`. Source files may
be text, Markdown, PDFs, images, or other documents Codex can inspect.

## Wiki Updates

When Jack asks to add, update, or refresh a wiki, complete the workflow without
asking him to operate another interface:

1. Resolve the target wiki and named source material.
2. Preserve new material under `vault/Sources/<wiki-id>/`. Move a supplied Inbox
   file there without changing its contents. When Jack supplies notes in the
   conversation, save the notes verbatim as a dated Markdown source.
3. Read the target wiki and its source files. Use only claims grounded in those
   sources or clearly identified existing wiki material.
4. Edit the wiki Markdown directly. Preserve accurate existing material,
   reconcile conflicts, and remove claims contradicted by newer authoritative
   sources.
5. Maintain a final `## Sources` section with relative links of the form
   `Sources/<wiki-id>/<filename>`.
6. Inspect the finished page for fidelity and run
   `uv run python scripts/wiki_validate.py`.

If the target or source relationship is genuinely ambiguous, ask Jack. Otherwise
proceed from the request and repository context.

## Source Rules

- Source files are canonical originals. Do not rewrite their contents to make a
  wiki claim easier to support.
- An Inbox file is not assigned until Jack names its target or the relationship
  is unambiguous from the request.
- Do not silently use sources from another wiki folder.
- If one source genuinely needs to support multiple wikis, ask before changing
  the simple one-folder ownership convention.
- Do not recreate SourceRecords, fact ledgers, lifecycle flags, model routing,
  provider calls, or a source-staging system.

## Development

Prefer deletion and simple filesystem conventions over new infrastructure.
Before implementing a feature, decide whether the real need can be handled by
the source folders, Markdown, agent instructions, or the validator.

Keep `scripts/wiki_validate.py` small and standard-library-only. Add tooling only
after repeated real use demonstrates a need.

## Commands

- Validation: `uv run python scripts/wiki_validate.py`
- Tests: `uv run pytest`
- Lint: `uv run ruff check scripts tests`
