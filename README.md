# MEMEX

MEMEX is a deliberately small, source-grounded Markdown wiki maintained by
Codex.

```text
source file -> Codex -> wiki Markdown
```

There is no dashboard or embedded LLM service. Source files and finished wiki
pages are the system.

## Layout

```text
vault/
├── Sources/
│   ├── Inbox/                 # drop new material here
│   └── <wiki-id>/             # originals used by one wiki
└── <wiki-id>.md               # finished wiki page
```

The private contents of `vault/` are ignored by Git. The tracked `.gitkeep`
files retain the empty folder structure in a fresh checkout.

## Normal Use

1. Put a document in `vault/Sources/Inbox/`, attach it to the Codex conversation,
   provide its local path, or paste notes directly.
2. Ask Codex to update a named wiki.
3. Codex preserves the source, edits the wiki, maintains its `## Sources` links,
   and validates the result.

Example:

```text
Use the new source in Inbox to update Home Lab.
```

See [docs/wiki-update-runbook.md](docs/wiki-update-runbook.md) for the exact
agent workflow.

## Validation

```bash
uv run python scripts/wiki_validate.py
```

The validator checks source placement, source links, Inbox state, legacy-state
removal, and obsolete generated markers.

Run the tests with:

```bash
uv run pytest
```
