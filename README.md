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

## Synchronization and external LLM access

The private vault is also materialized on dedicated Proxmox LXC 118:

```text
Obsidian desktop / phone
          ↓ Self-hosted LiveSync
      CouchDB 3.5.2
          ↓ official LiveSync CLI 1.0.15
  /srv/memex/vault
          ↓ read-only Markdown tools
      MEMEX MCP
```

CouchDB is transport state, not the source of truth. Notes remain ordinary files,
and the headless client keeps a complete server-side vault for MCP and backup.
The MCP recursively exposes every user `.md` file regardless of whether it was
created by MEMEX, Obsidian desktop, or a phone. Obsidian/LiveSync internal state
and recovery flag files are excluded.

- LiveSync: `https://obsidian.jackshome.com`
- Streamable HTTP MCP: `https://memex.jackshome.com/mcp`
- Unauthenticated health check: `https://memex.jackshome.com/health`

MCP clients must send `Authorization: Bearer <token>`. The token and CouchDB
credentials are stored only in `.local-backups/memex-service.env` (mode `0600`).

The desktop, phone, and headless client are pinned together to Self-hosted
LiveSync 1.0.15. For a new device, install that same version in a new empty
vault and use the encrypted URI and passphrase from
`.local-backups/livesync-client-setup.txt` (or scan
`.local-backups/livesync-client-setup.png`). Treat both setup artifacts as
credentials and choose the established remote as the source of truth.

Deployment and recovery details are in `deploy/README.md`.
