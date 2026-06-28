# data

Local state for MEMEX V2.

This directory is intentionally local-user state. Source records, preserved
source originals, ledgers, and registries may contain private information and
are ignored by Git by default. A fresh clone starts empty so each user can build
their own wikis.

Expected contents include source records, extracted facts, the wiki registry,
and the central wiki ledger.

Current V2 JSON layout:

- `data/wiki-ledger.json` stores assignments, review decisions, and baselines.
- `data/wiki-registry.json` stores stable wiki ids, titles, optional wiki
  descriptions/intentions, and vault paths.
- `data/sources/<escaped-source-id>.json` stores one source record per file.

Runtime scratch files should go under ignored subdirectories such as
`data/runtime/`, `data/tmp/`, or `data/cache/`.
