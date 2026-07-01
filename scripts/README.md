# scripts

Developer utilities and maintenance helpers for MEMEX.

Use scripts for rare operations such as wiki rename, merge, split, or cleanup
when those actions do not belong in the regular UI.

Current developer workflow:

```bash
python scripts/wiki_dev.py --help
python scripts/wiki_extract.py --help
```

Use `python scripts/wiki_server.py` for the usual local dashboard. It clears
stale MEMEX dashboard processes on any port plus anything listening on the
canonical dashboard port, then starts a fresh server at
`http://127.0.0.1:8765/`. Alternate dashboard ports are rejected by the start
script.

Use it to register a wiki from scripts, import source JSON or extract a local
text/Markdown file into a source record, assign a source, inspect
dashboard/status/review deltas, serve the local dashboard UI, apply review
decisions directly, through fixture provider JSON, or with OpenRouter
structured outputs, then build a vault markdown page.

The dashboard can create wikis interactively from a name and description; it
derives the internal id and Obsidian markdown file path. Use
`add-wiki --description` when you want scripted wiki creation with the same
intention text used by provider review. LLM review is source-scoped and
currently uses OpenRouter:

```bash
python scripts/wiki_dev.py review-llm WIKI_ID SOURCE_ID
```

Wiki builds are also provider-backed and use OpenRouter
`deepseek/deepseek-v4-pro` by default:

```bash
python scripts/wiki_dev.py build WIKI_ID
```

Use `build --fixture` only for deterministic local smoke tests.

The local dashboard uses one Add Source path: choose a runnable extraction
model, upload a source file, extract it, then assign the saved source to wikis
after the facts are visible. Use `scripts/wiki_extract.py` when you
specifically want local-path CLI extraction.

Use `python scripts/wiki_dev.py model-profiles` to inspect direct Anthropic,
OpenAI, and Google Gemini source-extraction candidates and credential readiness
without printing secrets. The command also shows the enabled extraction
profiles, schema contract, and default format routes. Sonnet 4.6 is the
default route for all current format families; GPT-5.5 and Gemini 3.5 Flash are
runnable alternate choices from the dashboard and CLI.

Use `python scripts/wiki_extract.py SOURCE_ID PATH` to run direct-provider
extraction and save the normalized source record. The first supported inputs
are text/Markdown-like files, PDFs, and images. Pass `--model` to choose a
specific enabled profile. Pass `--allow-duplicate` with a distinct `SOURCE_ID` when you
intentionally want a fresh extraction for the same original file.

Use `python scripts/wiki_validate.py` to validate source records, source asset
manifests, original-file hashes, evidence references, and ledger references.

Use `python scripts/wiki_costs.py --days 7` to fetch aggregate direct-provider
cost reports through OpenAI and Anthropic admin APIs.

Use `python scripts/wiki_costs.py --balances` to show provider balance links
and OpenRouter remaining credits from the same logic used by the local
dashboard header. OpenAI, Anthropic, and Google use the `Balance` label;
OpenRouter shows the API-reported dollar balance directly.
