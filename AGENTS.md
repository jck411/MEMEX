# MEMEX Agent Guide

MEMEX is a source library and a set of source-grounded Markdown wikis. Hermes is
the preferred authoring assistant; Codex remains a fallback. The authorized
assistant reads original references and edits wiki Markdown directly.

```text
original references -> authorized assistant -> cited wiki Markdown
```

There is no dashboard, model-provider API, semantic extraction database, review
ledger, or generated wiki build state. CouchDB exists only as LiveSync transport;
the materialized Markdown vault remains canonical.

## Layout

- `vault/<context>/` contains notes exposed through that folder's independent MCP
  context; `Sources/` and `Temp/` are reserved exceptions.
- `vault/Sources/Inbox/` is the drop location for new material.
- `vault/Sources/<domain>/<reference-id>/` preserves originals shared by wikis
  within that top-level domain; retain versions and stable filenames.
- `vault/<domain>/` contains nested subject wikis and ordinary navigation notes.
- `vault/Temp/` contains synchronized scratch notes excluded from MCP results.
- `vault/<wiki-id>.md` is the finished wiki page.

Nested wikis opt into validation with the exact standalone `<!-- memex:wiki -->`
line immediately after the title (blank lines allowed). Unmarked indexes and
ordinary notes are not evidence wikis. Legacy root `<wiki-id>.md` pages paired
with `Sources/<wiki-id>/` remain supported without a marker. Source files may
be text, Markdown, PDFs, images, or other documents the assistant can inspect.
The vault may live outside the checkout; use its actual path, not another sync client.

## Wiki Updates

When Jack asks to add, update, or refresh a wiki, complete the workflow without
asking him to operate another interface:

1. Resolve the target wiki and named source material from Inbox, a local or
   attached file, conversation notes, or an existing source.
2. Preserve new material under `vault/Sources/<domain>/<reference-id>/`: move an Inbox file,
   copy an external file, or save conversation notes verbatim as dated Markdown.
   Use a stable filename and never overwrite a different source silently.
3. Read the target wiki and actual source files. Ground claims in inspected
   references, not model memory, web substitutes, or unverified existing prose.
   Record title, version/date, page/section and applicability where available.
   Epic PDFs and excerpts may be proprietary and unavailable online. Preserve
   excerpts verbatim, label their limited scope, and inspect diagrams when relevant.
4. Edit the wiki Markdown directly. Preserve accurate existing material,
   include only material relevant to its subject, represent uncertainty, and
   reconcile conflicts or newer authoritative information.
5. Maintain a final `## Sources` section with links relative to the wiki's parent
   into `Sources/<domain>/`; include claim-level page/section citations where useful.
   Encode spaces/parentheses in inline Markdown destinations; PDF `#page=N`
   fragments identify physical pages. See README for supported link syntax.
6. Inspect the finished page for fidelity and run
   `python3 scripts/wiki_validate.py --vault-root /actual/vault/path`.
   Structural validation does not verify claim accuracy or PDF page correctness.
   Update the subject index when adding a wiki. Direct updates are the default;
   no separate preview approval is required for a requested wiki update.

If the target or source relationship is genuinely ambiguous, ask Jack. Otherwise
proceed from the request and repository context.

Report the target wiki, source preserved or reused, important changes or
unresolved conflicts, final path, and validation result.

## Source Rules

- Source files are canonical originals. Do not rewrite their contents to make a
  wiki claim easier to support.
- The vault is private. Preserve relevant personal and device identifiers Jack
  provides, including phone numbers, addresses, device IDs, and account
  identifiers; do not omit them solely for privacy. Keep passwords, API tokens,
  recovery codes, and other live credentials in authorized Git-ignored secret
  storage rather than versioned Markdown.
- An Inbox file is not assigned until Jack names its target or the relationship
  is unambiguous from the request.
- Reuse one original across wikis in the same top-level domain. Do not silently
  cross domain ownership boundaries or duplicate originals per wiki. Legacy
  root wikis retain their original source-folder ownership.
- Keep scratch notes and temporary extraction work under `Temp/`; never
  automatically promote them to evidence or delete them. Persistent derived
  reference caches belong with their original under `Sources/` and must be
  clearly distinguished from originals and cited if retained as assigned files.
- Inventory existing paths and links, preserve a recoverable backup, and scope
  live migrations separately. Do not overwrite populated destinations.
- Do not add databases, lifecycle state, model-provider calls, or another user
  interface without a repeated workflow demonstrating the need.

## Development

Prefer deletion and simple filesystem conventions over new infrastructure.
Before implementing a feature, decide whether the real need can be handled by
the source folders, Markdown, agent instructions, or the validator.

Keep `scripts/wiki_validate.py` small and standard-library-only. Add tooling only
after repeated real use demonstrates a need.

## Companion Service Boundary

- MEMEX owns the source-grounded wiki workflow, source layout, validator, and
  local private vault.
- The separate `obsidian-vault-service` repository owns CouchDB, headless
  LiveSync, the server-side vault mirror, read-only Markdown MCP, deployment,
  credentials, and backups on LXC 118.
- Do not add synchronization, remote access, authentication, or deployment code
  here. Coordinate cross-repository contract changes explicitly.
- LiveSync remains transport rather than a backup; preserve independent vault
  archives before changing synchronization topology.
- MCP reads finished Markdown and ordinary notes within its selected domain,
  never global `Sources/` or `Temp/`. General MCP is root-Markdown-only. A wiki
  citation does not establish that the reader inspected an original. Authoring
  needs separately authorized filesystem access; do not make MCP writable.

## Commands

- Validation: `python3 scripts/wiki_validate.py --vault-root /actual/vault/path`
- Tests: `uv run pytest`
- Lint: `uv run ruff check scripts tests`
