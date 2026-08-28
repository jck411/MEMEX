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
│   └── <wiki-id>/             # sources for a general MCP wiki
├── <context>/                 # independent folder-rooted MCP
│   ├── Sources/
│   │   └── <wiki-id>/         # sources for a wiki in this context
│   ├── <wiki-id>.md           # source-grounded wiki
│   └── <ordinary-note>.md     # free-form note
├── Temp/                      # synchronized scratch notes hidden from MCP
└── <wiki-id>.md               # general MCP wiki
```

The vault root and each direct, non-hidden top-level folder are independent wiki
roots. A Markdown file directly inside one of those roots is a MEMEX wiki when
it has a matching `Sources/<wiki-id>/` folder in the same root. Markdown without
that source folder remains an ordinary note and is not validated as a wiki.

Root-level Markdown is available through the general MCP. Each top-level folder
is available through its own folder-bound MCP URL, and its notes are not
included in general retrieval or another folder's retrieval. Every wiki root's
`Sources/` directory and the top-level `Temp/` workspace are excluded from MCP
results. Top-level `Sources/` and `Temp/` are reserved and never receive folder
MCPs.

The private contents of `vault/` are ignored by Git. The tracked Inbox
placeholder retains the source drop location in a fresh checkout.

## Normal Use

1. Put a document in `vault/Sources/Inbox/`, attach it to the Codex conversation,
   provide its local path, or paste notes directly.
2. Ask Codex to update a named wiki.
3. Codex resolves the general or folder MCP context, preserves the source in
   that context's `Sources/<wiki-id>/`, edits the wiki, maintains its
   `## Sources` links, and validates the result.

Example:

```text
Use the new source in Inbox to update Home Lab.
Use these measurements to update the Shoes wiki in Health.
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

## Companion vault service

MEMEX owns the source-grounded wiki workflow and the private local `vault/`.
The separate `obsidian-vault-service` repository owns synchronization, the
server-side vault mirror, read-only MCP access, authentication, deployment, and
backups on Proxmox LXC 118.

```text
Obsidian phone / workstation apps
          ↕
  obsidian-vault-service
          ↓
  synchronized Markdown vault
```

Its local checkout is expected at
`/home/jack/REPOS/obsidian-vault-service`. Operational documentation and
Git-ignored recovery artifacts live there. MEMEX does not implement or deploy
the synchronization and access service.

For ordinary work on both the Markdown and MCP layers, open
`/home/jack/REPOS/MEMEX` and `/home/jack/REPOS/obsidian-vault-service` as a
two-root workspace. Use `vault/` in MEMEX for Markdown and
`obsidian_vault_service/` in the companion repository for MCP code.
