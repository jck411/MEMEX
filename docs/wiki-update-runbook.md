# Agent-Run Wiki Update Runbook

Use this runbook when Jack asks an agent to update, refresh, rebuild, or add
material to a MEMEX wiki. The agent owns the mechanical workflow and the final
quality check; Jack should not need to shepherd the dashboard steps.

## Convenient Request

The normal request is:

```text
Update <wiki> from <source or new material>.
```

Examples:

```text
Update Home Lab from the Proxmox server hardware source.
Refresh Home Lab after I update the hardware draft.
Add these notes to Jack's Biography and update the wiki: <notes or path>.
```

If the conversation and repository state identify the wiki and source, a short
request such as `update the wiki` is sufficient.

## Default Contract

An update request authorizes the agent to:

1. Inspect the target wiki description, assignments, current SourceRecords,
   preserved originals, ledger-derived status, and current markdown.
2. Choose the correct source operation using the rules below.
3. Assign the named source to the named wiki if that explicit relationship does
   not already exist.
4. Run LLM review for missing or stale fact decisions.
5. Build the wiki through the managed build workflow.
6. Validate persisted state and audit the resulting markdown against accepted
   facts and the source.

Provider-backed extraction, review, and build calls are normal implementation
steps for this request. Ask for clarification only when the target wiki or
source relationship cannot be resolved safely from the request and repository.

## Choose the Source Operation

Use the least complex operation that preserves source grounding:

- **Review and build only:** the SourceRecord is already complete and accurate;
  only decisions or the build are stale.
- **Repair:** a small number of extracted fields or facts are wrong, and every
  correction is directly supported by the preserved original. Repair through
  the workspace/dashboard workflow so fact signatures invalidate decisions by
  derivation.
- **Re-extract:** the preserved original is authoritative but extraction omitted
  material, combined unrelated claims, or produced generally poor coverage.
- **New source ingest:** Jack supplies new facts, notes, or a changed document
  that are not contained in the preserved original. Preserve them as a new
  source asset and SourceRecord; do not rewrite history by making the old
  original appear to contain them.

Do not patch a generated wiki to compensate for weak extraction. Fix the input
layer and let review and build propagate the change.

## Quality Gates

### Extraction

Before review, compare the SourceRecord with its original. Check that:

- durable, wiki-useful claims were not reduced to a shallow inventory
- operational roles, relationships, exceptions, and important uncertainty were
  retained when relevant
- facts are atomic enough to review independently
- every fact is grounded in preserved evidence
- time-sensitive observations are labeled or excluded appropriately

Fact count is diagnostic, not a target. A short source may need few facts; a
dense technical source should not collapse into a dozen generic statements.

### Review

- Review answers which source facts belong within the current wiki description.
- Do not accept facts solely because they appear in the source.
- Do not build while the wiki still has missing or stale review decisions.
- Preserve explicit manual decisions unless changed facts or scope have made
  them stale by derivation.

### Build

- Build only through `WikiWorkspace` or the existing dashboard/CLI workflow.
- The builder may update the managed synthesis section; it must not bypass
  review or write a successful baseline before the markdown write succeeds.
- Compare the final page with the accepted facts. A technically successful but
  materially incomplete, vague, or misleading page is not a completed update.

## Hard Boundaries

Never:

- hand-edit `data/wiki-ledger.json`
- hand-edit generated vault wiki prose
- store assignment, review, or build state in a source manifest
- mark a build current without a successful managed markdown write
- silently ground new claims in an old preserved original that does not contain
  them

Direct inspection of those files is expected; direct lifecycle mutation is not.

## Validation and Report

After persisted changes, run:

```text
uv run python scripts/wiki_validate.py
```

Run relevant targeted tests if code changed or a workflow fails. The handoff
should state:

- target wiki and source(s)
- whether the agent repaired, re-extracted, ingested, reviewed, or built
- important accepted, rejected, or unresolved material
- final markdown path and a short quality assessment
- validation or test result

If a provider or workflow fails, leave derived state honest and report the
remaining `needs_review` or `needs_build` condition instead of editing around
it.
