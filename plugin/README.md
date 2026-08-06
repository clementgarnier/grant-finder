# Grant Finder

A Claude Code plugin for grant prospecting: it combines historical IRS Form
990 grant-making data with public grant-opportunity data so Claude can find
funders and open opportunities for a nonprofit.

The commands below assume you're running them from the repo root (this
plugin's directory is `plugin/`; the MCP server implementations it points
at live in `../mcp-servers/`, not under the plugin itself - see "Why
`mcp-servers/` lives outside the plugin" below).

## What's included

- **`irs990-filings-grants`** (MCP) - GraphQL over IRS Form 990 filings and
  the grants they report (Schedule I / Part XV). Code lives at
  `mcp-servers/irs-990/server.py` - see `mcp-servers/irs-990/README.md`.
- **`grants-gov`** (MCP) - GraphQL over grant opportunities, backed live by
  the Simpler Grants API (`api.simpler.grants.gov`)
  (`mcp-servers/grants-gov/server.py`). Requires a `SIMPLER_GRANTS_API_KEY` -
  see `mcp-servers/grants-gov/README.md`.
- **Skills** - `find-private-foundation-opportunities`, `find-federal-opportunities`,
  `find-state-local-opportunities` (web search only - no connector covers
  state, county and city grant programs), `funder-due-diligence`, and the
  combined `grant-prospecting-report`.

Both connectors expose a single `graphql(query, variables)` tool each, so
skills use one consistent querying idiom across both.

## Why `mcp-servers/` lives outside the plugin

The plugin itself only needs `.claude-plugin/plugin.json`, `.mcp.json`, and
`skills/` - those are what Claude Code's plugin format actually looks for.
`.mcp.json` just holds URLs; it doesn't care where the server processes
behind those URLs live. So the server implementations sit at the repo root
in `mcp-servers/`, alongside `scripts/` and `docker/`, rather than nested
inside `plugin/`.

## Local Cowork setup

1. Start the IRS 990 connector: `docker compose up -d`
2. Start the grants-gov connector (after
   `pip install -r mcp-servers/grants-gov/requirements.txt` and setting
   `SIMPLER_GRANTS_API_KEY` in `.env` or your shell - see
   `mcp-servers/grants-gov/README.md`):
   `python3 mcp-servers/grants-gov/server.py`
3. Generate the dev MCP config: `scripts/generate-plugin.sh dev`
4. Zip the plugin directory (`zip -r grant-finder.zip plugin` from the
   repo root) and upload it from Customize -> Plugins in Claude Desktop,
   rather than installing from a marketplace. There's no CLI equivalent
   of Claude Code's `--plugin-dir` for Cowork, so pick up edits by
   re-zipping and re-uploading rather than reloading in place.

Re-run step 3 any time `.mcp.json` needs regenerating (it's a generated,
committed file - see below).

## Releasing

Once both connectors are deployed as hosted services:

1. Update the hosted URLs in `plugin/mcp.config.release.json`
2. `scripts/generate-plugin.sh release`
3. Commit the resulting `.mcp.json`, tag, and publish via the marketplace

`plugin/.mcp.json` is intentionally committed rather than gitignored -
Claude Code reads it directly from the plugin's published source, so
whatever's committed at release time is what installers get. Iterate
locally with the `dev` config; only the `release` config should be what's
committed right before a tag.

A tracked pre-commit hook (`.githooks/pre-commit`) blocks any commit that
stages `plugin/.mcp.json` when it doesn't match `mcp.config.release.json`,
so an in-progress `dev` config can't slip into a commit by accident.
Enable it once per clone:

```bash
git config core.hooksPath .githooks
```
