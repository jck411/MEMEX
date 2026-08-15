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

The private contents of `vault/` are ignored by Git. The tracked Inbox
placeholder retains the source drop location in a fresh checkout.

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

## Validation

```bash
uv run python scripts/wiki_validate.py
```

The validator checks wiki structure, source placement, source links, and Inbox
state.

Run the tests with:

```bash
uv run pytest
```
