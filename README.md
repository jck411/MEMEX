# MEMEX

MEMEX is a deliberately small, reference-first library of domain wikis.
Hermes is the preferred authoring agent; Codex is a fallback. Agents read private
references and edit finished Markdown directly, without an embedded LLM.

## Hierarchical domain wikis

Use one top-level folder per retrieval domain, with as many nested wikis as the
subject needs. Originals live once in that domain's shared reference library:

```text
vault/                        # may live outside this checkout
├── Clinical/
│   ├── index.md              # navigation, not an evidence wiki
│   └── Epic/
│       ├── Orders.md         # marked wiki
│       └── Training.md       # marked wiki; may reuse the same reference
├── Sources/
│   ├── Inbox/                # unassigned incoming originals
│   └── Clinical/Epic/        # private PDFs, excerpts, versioned originals
└── Temp/                     # scratch, never automatically promoted/deleted
```

A nested wiki opts in with the exact standalone `<!-- memex:wiki -->` line
immediately after its title (blank lines are allowed). Ordinary notes and
`index.md` navigation pages have no marker and are not evidence wikis. A marked
page, including a marked index, is validated as a wiki. Example for
`Clinical/Epic/Orders.md` (illustrative paths, not Epic guidance):

```markdown
# Orders
<!-- memex:wiki -->

Write only claims verified against the supplied references here.

## Sources
- [Guide, supplied version, page 7](../../Sources/Clinical/Epic/Guide%20%28v1%29.pdf#page=7)
```

Links resolve relative to the wiki's parent directory. Any number of wikis in
`Clinical/` may cite `Sources/Clinical/`, at any depth; another top-level domain
cannot. Use standard inline Markdown links, URL-encode spaces/parentheses and
literal `#` (`%23`) in filenames, and append `#page=N` for PDF provenance.
Angle-bracket destinations also support literal spaces and parentheses.
Obsidian wikilinks, reference-style links, link titles, and bare unescaped
parentheses are not supported by the small validator.

## Reference-first authoring

1. Ask Hermes (or Codex) to update a named wiki using named local references,
   attached PDFs, Inbox files, or supplied excerpts. Agents need direct authorized
   filesystem access: retrieval MCP deliberately cannot read the source library.
2. Reuse an existing original; preserve genuinely new material once under
   `Sources/<domain>/...`. Never overwrite another version or clone one PDF per
   wiki. Keep supplied excerpts verbatim and label their limited scope.
3. Read the actual references before editing. For specialized Epic material,
   retain document title, supplied version/date, relevant pages, and local-build
   applicability. Do not invent Epic behavior from model memory or treat another
   wiki as primary evidence. Record gaps and conflicts explicitly.
4. Edit the finished wiki directly; maintain its final `## Sources` section and
   claim-level citations where needed. Keep experiments/extractions in `Temp/`.
5. Check source fidelity manually, then run the structural validator.

### Non-destructive organization

Inspect existing domain indexes before adding topics. Update an unmarked index
with navigation links; do not treat it as evidence. Keep original versions and
excerpt provenance intact. Migration is separately scoped work: inventory paths
and incoming links, obtain a recoverable backup, preserve populated destinations,
and update relative links only after an authorized move. Never automatically
delete or promote `Temp/`. This change performs no live migration.


## External vault and checks

```bash
python3 scripts/wiki_validate.py --vault-root /absolute/path/to/vault
# Backward-compatible checkout-local layout:
python3 scripts/wiki_validate.py --repo-root /absolute/path/to/MEMEX
```

The root options are mutually exclusive. With neither, the default is this
checkout's `vault/`, independent of the current working directory. The validator
is standard-library-only (Python 3.11+), read-only, and does not require uv.

It checks one title, marker placement for nested wikis, one final `## Sources`,
nonempty source links, relative destinations, existing files, domain ownership,
and unreferenced assigned sources. Unassigned Inbox files warn; missing vault,
Sources, Inbox, or all wikis fail. Every non-dot source file outside Inbox must
be linked by at least one owning wiki. Symlinks anywhere inside the vault are
rejected before wiki reads (counts are zero on this early failure); the chosen
vault root itself is resolved. Errors exit 1; warnings alone do not fail.

This is structural validation, **not proof of source fidelity**, medical
correctness, PDF page existence, completeness, or MCP deployment correctness.
It uses a restricted Markdown convention, not a full Markdown parser. Run on a
stable local snapshot; it is not a hostile-filesystem security sandbox.

Development checks:

```bash
uv run pytest
uv run ruff check scripts tests
# If uv is unavailable:
python3 -m venv .venv
.venv/bin/pip install 'pytest>=9,<10' 'ruff>=0.15.20'
.venv/bin/pytest
.venv/bin/ruff check scripts tests
```

## Legacy layout and service contract

The existing root wiki/source pairing below remains supported without markers.
The companion service must expose finished domain Markdown (including navigation)
but exclude `Sources/` and `Temp/` from retrieval. The marker controls validation,
not MCP authorization. MEMEX does not deploy or verify that separate service's
filters. No sync client, embedded model service, or automatic migration is added.

## Legacy layout

```text
vault/
├── <context>/                 # independent folder-rooted MCP notes
├── Sources/
│   ├── Inbox/                 # drop new material here
│   └── <wiki-id>/             # originals used by one wiki
├── Temp/                     # synchronized scratch notes hidden from MCP
└── <wiki-id>.md               # finished wiki page
```

A root Markdown file is a MEMEX wiki when it has a matching
`Sources/<wiki-id>/` folder. Other synchronized Obsidian notes may coexist in
the vault and are not interpreted as MEMEX wikis. Markdown below the top-level
`Temp/` folder is synchronized but excluded from the read-only MCP service.
Root-level Markdown is available through the general MCP. Each other direct,
non-hidden top-level folder is available through its own folder-bound MCP URL;
its notes are not included in general retrieval or another folder's retrieval.
`Sources/` and `Temp/` are reserved and never receive folder MCPs.

The private contents of `vault/` are ignored by Git. The tracked Inbox
placeholder retains the source drop location in a fresh checkout.

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

Locate the companion checkout on the current machine rather than assuming a
workstation path. Operational documentation and Git-ignored recovery artifacts
belong there. MEMEX does not implement or deploy synchronization or access.
Use the actual synchronized vault path with `--vault-root`; do not create another
sync client or copy the live vault into Git to fit the checkout layout.
