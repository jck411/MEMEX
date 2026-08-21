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

A root Markdown file is a MEMEX wiki when it has a matching
`Sources/<wiki-id>/` folder. Other synchronized Obsidian notes may coexist in
the vault and are not interpreted as MEMEX wikis.

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

## Companion vault service

MEMEX owns the source-grounded wiki workflow and the private local `vault/`.
The separate `obsidian-vault-service` repository owns synchronization, the
server-side vault mirror, read-only MCP access, authentication, deployment, and
backups on Proxmox LXC 118.

```text
Obsidian phone / event-triggered workstation CLI
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
