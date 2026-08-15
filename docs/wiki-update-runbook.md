# Codex Wiki Update Runbook

Use this runbook whenever Jack asks Codex to add material to a wiki, refresh a
wiki, or process a source.

## Request Contract

The normal request is:

```text
Use <source> to update <wiki>.
```

A short request such as `process the Inbox source for Home Lab` is sufficient
when the target and source are clear.

## 1. Resolve Material

Inspect the target page, `vault/Sources/Inbox/`, and
`vault/Sources/<wiki-id>/`. Determine whether the request uses:

- a file already in Inbox
- a local file path or attached file
- notes supplied in the conversation
- an existing source that changed
- existing sources for a requested refresh

Ask only when assigning the material to a wiki would require guessing.

## 2. Preserve the Source

The canonical source location is `vault/Sources/<wiki-id>/`.

- Move an Inbox file into the target folder without changing its bytes.
- Copy an external local file into the target folder before using it.
- Save conversation notes verbatim as a dated Markdown file. Add only a short
  heading identifying them as supplied notes; do not paraphrase the source.
- Use a clear, stable filename. Never overwrite a different source silently.

Do not manufacture extracted-fact files, summaries, ledgers, or intermediate
drafts.

## 3. Update the Wiki

Read the current page and every relevant source in the target folder. Then edit
`vault/<wiki-id>.md` directly.

- Preserve accurate existing material.
- Add useful claims supported by the new source.
- Reconcile newer information with older claims rather than appending
  contradictions.
- Represent uncertainty and time-sensitive observations honestly.
- Do not include a claim merely because it appears in a source; it must also
  belong within the wiki's subject.
- Do not invent provenance, dates, relationships, or conclusions.

The page must start with one level-one title and end with a `## Sources` section.
Use ordinary relative Markdown links:

```markdown
## Sources

- [Readable source name](Sources/<wiki-id>/<filename>)
```

The source list is the assignment and provenance record. No other database is
updated.

## 4. Inspect and Validate

Compare the finished page with the source material. Check coverage, fidelity,
conflicts, and whether every source link resolves. Then run:

```text
uv run python scripts/wiki_validate.py
```

Inbox warnings are allowed when unrelated files are awaiting future work.
Validation errors must be fixed before reporting completion.

## Report

State:

- target wiki
- source file preserved or reused
- important material added, changed, or left unresolved
- final wiki path
- validation result
