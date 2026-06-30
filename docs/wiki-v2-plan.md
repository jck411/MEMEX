# MEMEX Wiki V2 Plan

Last updated: 2026-06-30

## Direction

MEMEX is a Wiki LLM. It turns source material into persistent markdown wikis
instead of doing classic RAG at question time.

The core loop is:

```text
source -> extracted facts -> source-to-wiki assignment -> per-wiki fact review
-> accepted fact delta -> markdown wiki build
```

The wiki is the product. Sources, ledgers, manifests, provider calls, and the
dashboard exist to keep the markdown wikis accurate, inspectable, and
source-grounded.

## Architecture Rules

- Wiki assignment is manual through source/wiki bubbles.
- No domains, sensitivity tags, categories, auto-populate, or word matching for
  wiki routing.
- Source manifests must never store wiki assignment or review state.
- `needs_review`, `needs_build`, and `current` are derived, not stored.
- The central wiki ledger owns assignments, fact decisions, and build baselines.
- Source review does not update a wiki build baseline.
- Build baselines update only after successful markdown writes.
- Vault wiki markdown is managed output. Humans do not hand-edit wiki files;
  wiki changes are written by code or LLM build workflows.
- Legacy code in `/home/jack/MEMEX-legacy-2026-06-22/` is borrow-only reference.

## Implemented Baseline

The V2 foundation is in place:

- Persistence is split across registry, ledger, SourceRecords, source asset
  manifests/originals, and markdown vault output.
- `python scripts/wiki_server.py` runs the local dashboard.
- The dashboard supports ingest, source detail, assignment bubbles, manual
  review, LLM review, manual source repair, source-level LLM source fix, source
  re-extraction, wiki descriptions, wiki creation/deletion, provider balances,
  source delete, and wiki build actions.
- Upload, typed text, CLI local-path extraction, and deterministic text import
  preserve originals before extraction and deduplicate byte-identical originals
  by SHA256.
- Shared extraction supports text/Markdown-like files, PDFs, and images through
  direct Anthropic, OpenAI Responses, and Google Gemini adapters.
- Manual source repair and source-level LLM source fix edit SourceRecords while
  preserved originals and source asset manifests remain authoritative.
- Per-wiki LLM review uses OpenRouter `deepseek/deepseek-v4-pro` for one
  assigned source/wiki pair and writes to the same ledger state as manual
  checkboxes.
- Wiki builds use OpenRouter `deepseek/deepseek-v4-pro` to consolidate current
  accepted facts into plain claims, then synthesize a managed wiki body from
  those claims. LLM-built wiki synthesis remains separate from downstream LLM
  use of the finished markdown.
- Build packets group accepted facts by source for reconciliation, but finished
  vault markdown intentionally omits source inventories, fact ids, citations,
  rejected facts, and review audit appendices. Each built wiki includes a
  generated `MEMEX Provenance` section with a relative link to its facts-used
  page.
- Dashboard wiki pages link to a wiki facts inspection page that shows current
  accepted facts and not-used facts grouped by source, with links back to source
  detail pages.
- `python scripts/wiki_validate.py` validates source records, source assets,
  originals, evidence references, and ledger references.

## Current Semantics

Review answers:

```text
Which facts from this assigned source belong in this wiki?
```

Review deltas include assigned facts with missing or stale decisions. Manual
tick/untick changes do not require LLM review; they only affect build state.

Build answers:

```text
Given the accepted fact state changed, how should this wiki markdown change?
```

Build must not redo relevance. Relevance belongs to review.

Humans change wiki inputs: source assignment, fact review, source repair, and
wiki description scope. Code and LLM build workflows write the vault wiki
markdown.

Wiki description changes are scope changes:

- `WikiRecord.description` is stored in the central registry.
- Decisions from the old scope become stale by derivation.
- Accepted facts from the old scope are excluded from the current build
  fingerprint.
- Wikis with stale review are not buildable until review is current.
- Build prompts include the current wiki description when configured; generated
  markdown stays clean external-facing prose.

## Next Development Priorities

### 1. Wiki Build Refinement

Goal: make builds trustworthy enough that the markdown vault becomes the main
working surface.

Needed:

- Build from accepted fact deltas plus existing markdown.
- Preserve existing managed markdown around generated sections.
- Keep provider-backed `Wiki Brief` synthesis as the only generated prose
  section.
- Consolidate accepted facts into claims before asking for polished wiki prose.
- Keep provenance visible enough to audit generated claims without embedding
  detailed fact inventories in the vault markdown.
- Update build baselines only after successful writes.
- Make failed builds leave no partial baseline or misleading `current` state.

Design preference:

- Keep build orchestration separate from markdown rendering and vault writes.
- Prefer a small generated-section contract over whole-page rewrites.
- Treat the existing markdown file as input, not disposable output.

### 2. Provenance And Evidence UX

Goal: make it easy to inspect why a wiki claim exists and which source fact
supports it.

Needed:

- Deepen source/fact provenance links with source-detail and evidence-level
  navigation.
- Show source asset metadata and original artifact access from source detail.
- Keep provenance data in ledgers/manifests, not duplicated into markdown as
  hidden lifecycle state.

Design preference:

- Markdown should be readable outside the app and clean for external
  consumption.
- Provenance should be auditable without making every paragraph noisy.

### 3. Review Queue And Bulk Work

Goal: make normal operation obvious when many sources and wikis exist.

Needed:

- A dashboard queue for sources/wikis with derived `needs_review`.
- A dashboard queue for wikis with derived `needs_build`.
- Batch-friendly review/build actions that still preserve explicit assignment
  and review semantics.
- Clear empty/error states for missing source assets, invalid ledger references,
  and stale decisions.

Design preference:

- Derived state should come from the registry, ledger, source records, and build
  baselines at read time.
- Avoid storing lifecycle flags just to make the UI easier.

### 4. Wiki Administration

Goal: support active development of wiki boundaries without entangling it with
source ingest.

Needed:

- Rename, split, and merge wiki records.
- Migrate assignments, decisions, and build baselines between wiki ids when
  explicitly requested.
- Keep identity-changing wiki administration as development tooling until the
  dashboard workflow is genuinely needed.

Design preference:

- Wiki identity should remain stable and explicit.
- Migration scripts should be boring, validated, and reversible from git.

## Backlog

- Audit OpenRouter prompt/schema workflows so prompt payloads contain task data
  only, JSON shape lives in `response_format`, shared provider settings stay
  consistent, and Python validators enforce domain-specific semantics.
- Source original preview/download in the dashboard.
- Better source/fact search across the local corpus.
- Cost and usage reporting by provider/model/source.
- Failed-provider debug artifacts for extraction and review.
- Repair scripts for common validation failures.
- Import/export utilities for moving a wiki project between machines.

## Keep Out

- Domain-based routing.
- Sensitivity/privacy routing.
- Auto-populate or word matching.
- Source manifests as wiki metadata.
- Stored `needs_review`, `needs_build`, or `current` flags.
- V1 compatibility branches.
- Row-level LLM repair buttons.
- Dashboard UI for every development-only operation before the workflow is
  stable.

## Development Loop

For implementation work:

1. Inspect the relevant subsystem before editing.
2. Delete, simplify, replace, or refactor before patching old code.
3. Keep source extraction, wiki state, markdown output, UI, validation, and LLM
   orchestration as separate responsibilities.
4. Run `python scripts/wiki_validate.py` when state shape or persistence changes.
5. Run targeted `uv run pytest ...` tests for touched code paths.
6. Update this plan only when the direction or future work changes.
