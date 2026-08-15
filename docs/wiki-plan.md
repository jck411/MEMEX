# MEMEX Direction

Last updated: 2026-08-15

## Purpose

MEMEX is a private, source-grounded Markdown wiki maintained through Codex.
Its complete loop is:

```text
Jack supplies a source -> Codex preserves and reads it -> Codex updates a wiki
```

The source files and wiki pages are the durable product. Everything else should
remain small enough to understand at a glance.

## Architecture

- New material arrives in `vault/Sources/Inbox/`.
- Processed originals live in `vault/Sources/<wiki-id>/`.
- Finished pages live at `vault/<wiki-id>.md`.
- A page's final `## Sources` links declare which originals ground it.
- Codex edits pages directly and validates the result.
- Git ignores the private vault contents.

There is intentionally no:

- dashboard or web server
- embedded model provider
- extracted-fact database
- assignment or review ledger
- build baseline or lifecycle status
- model profile, cost monitor, or API-key runtime
- generated-section protocol

## Product Rule

Do not add infrastructure for hypothetical scale. If normal use reveals a
repeated problem, solve that specific problem with the smallest filesystem,
Markdown, instruction, or validation change that works.

## Current Priorities

- Add grounded sources for Jack's Biography and Jack's Identity.
- Continue improving the existing Home Lab, ThinkPad, worldview, and operating
  principles pages from preserved originals.
- Refine the source-folder workflow only when actual use exposes friction.
