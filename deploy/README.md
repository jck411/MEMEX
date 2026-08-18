# MEMEX server deployment

MEMEX runs in dedicated, unprivileged Debian 13 Proxmox LXC 118 at
`192.168.1.118` with 2 vCPU, 2 GiB RAM, and a 16 GiB root disk.

The deployment keeps three responsibilities separate:

- CouchDB is the Self-hosted LiveSync remote on port `5984`.
- The official LiveSync CLI mirrors CouchDB into `/srv/memex/vault`.
- The read-only MCP service exposes all user Markdown on port `9020`.

## Runtime layout

```text
/opt/memex/                   application checkout/deployment files
/srv/memex/couchdb/          CouchDB data
/srv/memex/couchdb-config/   persisted CouchDB configuration
/srv/memex/livesync/         headless CLI local database
/srv/memex/livesync-config/  generated LiveSync settings
/srv/memex/vault/            materialized Obsidian vault
/srv/memex/backups/          rolling daily vault archives (30 days)
```

Copy `.env.example` to `.env`, replace every placeholder, and keep `.env` mode
`0600`. Then run:

```bash
sudo apt-get install -y docker.io docker-compose curl jq
sudo systemctl enable --now docker
sudo ./deploy/bootstrap.sh
```

The MCP health endpoint is `http://192.168.1.118:9020/health`. MCP clients use
`http://192.168.1.118:9020/mcp` with `Authorization: Bearer <token>`.

`bootstrap.sh` normalizes mirrored Markdown to mode `0644` so the unprivileged,
read-only MCP container can read imported notes. It does not change permissions
on LiveSync databases, configuration, credentials, or other non-Markdown files.

Do not expose ports with router forwarding. Public HTTPS belongs in the NETWORK
repository's named Cloudflare Tunnel configuration.

## Client setup

Use the same CouchDB URL, database, user, password, and LiveSync encryption
passphrase on every Obsidian device. Generate and transfer a protected Setup URI
instead of sending those values separately. A setup URI plus its unlock
passphrase grants vault access, so store and transfer both as credentials.

Back up every existing vault before joining it to synchronization. Add new
devices from empty vaults and fetch from the established remote.

This deployment is pinned to Self-hosted LiveSync `1.0.15` on the desktop,
phone, and headless CLI. Do not update one client independently; perform a
coordinated upgrade of all three only after a verified vault backup.

The shared database uses the V3 Rabin-Karp splitter, `xxhash64`, a chunk-size
enhancement of `60`, and case-insensitive filename handling. Customisation and
hidden-file sync remain disabled; only ordinary vault files are synchronized.

For a coordinated upgrade:

1. Stop every Obsidian client and the headless CLI.
2. Back up each vault and take a recoverable snapshot of LXC 118.
3. Pin the same stable LiveSync version on every client and the CLI image.
4. Rebuild once from the chosen authoritative vault.
5. Reset every other client from that remote before unlocking normal sync.
6. Recreate the CLI local cache, resume it, and verify both sync directions and
   the authenticated MCP endpoint.

`memex-vault-backup.timer` creates a complete daily archive and retains 30
days. These same-container snapshots protect against replicated mistakes, but
they do not replace an off-host backup of CT 118.
