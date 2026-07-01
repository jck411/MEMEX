# MEMEX

MEMEX is a personal Wiki LLM. It turns source material into persistent markdown
wikis.

Current status: usable local app. The main development phase is source recovery
and wiki construction: put recovered old source material in
`/home/jack/MEMEX/data/source-drafts/`, extract useful drafts into source
records, assign sources to wikis, review facts, and build markdown pages.

Run the dashboard with:

```bash
uv run python scripts/wiki_server.py
```

The repository does not track generated wikis, source records, preserved source
originals, or local ledgers. Those files live under `vault/` and `data/` as
private local state so each user can build their own MEMEX.

Start with:

- [docs/wiki-plan.md](docs/wiki-plan.md)
- [AGENTS.md](AGENTS.md)
