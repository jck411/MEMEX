# MEMEX Agent Guide

MEMEX is a source library and a set of source-grounded Markdown wikis. Codex is
the only semantic processor: it reads sources, decides what belongs in a wiki,
and edits that wiki directly.

```text
source file -> Codex -> wiki Markdown
```

There is no dashboard, model-provider API, semantic extraction database, review
ledger, or generated wiki build state. CouchDB exists only as LiveSync transport;
the materialized Markdown vault remains canonical.

## Layout

- `vault/<context>/` contains notes exposed through that folder's independent MCP
  context; `Sources/` and `Temp/` are reserved exceptions.
- `vault/Sources/Inbox/` is the drop location for new material.
- `vault/Sources/<wiki-id>/` contains the original sources used by that wiki.
- `vault/Temp/` contains synchronized scratch notes excluded from MCP results.
- `vault/<wiki-id>.md` is the finished wiki page.

Source folder names and wiki filenames use the same `wiki-id`. Source files may
be text, Markdown, PDFs, images, or other documents Codex can inspect.
This paired folder-and-file convention identifies MEMEX wikis; unrelated
Obsidian Markdown may coexist in the vault without being validated as a wiki.
Folder-context notes are not MEMEX wikis and do not participate in source validation.

## Wiki Updates

When Jack asks to add, update, or refresh a wiki, complete the workflow without
asking him to operate another interface:

1. Resolve the target wiki and named source material from Inbox, a local or
   attached file, conversation notes, or an existing source.
2. Preserve new material under `vault/Sources/<wiki-id>/`: move an Inbox file,
   copy an external file, or save conversation notes verbatim as dated Markdown.
   Use a stable filename and never overwrite a different source silently.
3. Read the target wiki and its source files. Use only claims grounded in those
   sources or clearly identified existing wiki material.
4. Edit the wiki Markdown directly. Preserve accurate existing material,
   include only material relevant to its subject, represent uncertainty, and
   reconcile conflicts or newer authoritative information.
5. Maintain a final `## Sources` section with relative links of the form
   `Sources/<wiki-id>/<filename>`.
6. Inspect the finished page for fidelity and run
   `uv run python scripts/wiki_validate.py`.

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
- Do not silently use sources from another wiki folder.
- If one source genuinely needs to support multiple wikis, ask before changing
  the simple one-folder ownership convention.
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

## Commands

- Validation: `uv run python scripts/wiki_validate.py`
- Tests: `uv run pytest`
- Lint: `uv run ruff check scripts tests`
