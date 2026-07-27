# Grant Finder

A Claude Code plugin for grant prospecting: it combines historical IRS
Form 990 grant-making data with live public grant-opportunity data so
Claude can find funders and open opportunities for a nonprofit.

Given an organization's mission, sector, and location, Grant Finder can
identify private foundations that have historically funded similar
organizations, check those funders' current application windows, surface
open federal/public grant opportunities, and build due-diligence profiles
on specific funders - either individually or as one combined prospecting
report.

## Repo layout

- **`plugin/`** - the installable Claude Code plugin: manifest, MCP
  config, and skills. See [`plugin/README.md`](plugin/README.md).
- **`mcp-servers/`** - the two GraphQL-over-MCP connectors the plugin
  uses:
  - [`irs990-filings-grants`](mcp-servers/irs-990/README.md) - IRS Form
    990 filings and the grants they report (Schedule I / Part XV), served
    from a MySQL database.
  - [`grants-gov`](mcp-servers/grants-gov/README.md) - open grant
    opportunities, backed live by the Simpler Grants API
    (`api.simpler.grants.gov`).
- **`marketplace/`** - a local-path Claude Code plugin marketplace for
  installing `plugin/` during development. See
  [`marketplace/README.md`](marketplace/README.md).
- **`scripts/`** - `fetch_irs_990_files.py` and `build_mysql.py`, the
  pipeline that populates the IRS 990 MySQL database, plus
  `generate-plugin.sh` for stamping `plugin/.mcp.json`.
- **`docker/`** and **`docker-compose.yml`** - local dev containers for
  both connectors plus MySQL.
- **`deploy/app.yaml`** - DigitalOcean App Platform spec for deploying
  both connectors as hosted services.

## Quickstart

From the repo root, with `SIMPLER_GRANTS_API_KEY` and the MySQL
credentials set in a repo-root `.env` (see
[`mcp-servers/grants-gov/README.md`](mcp-servers/grants-gov/README.md)):

```bash
docker compose up -d
scripts/generate-plugin.sh dev
```

The `mysql` container starts with an empty `irs990` database. Populate it
by downloading the raw IRS 990 XML filings and loading them in:

```bash
.venv/bin/python3 scripts/fetch_irs_990_files.py   # downloads datasets/ from irs.gov
.venv/bin/python3 scripts/build_mysql.py            # parses + loads into MySQL
```

**Caveat:** this is a one-time bulk pipeline over several years of IRS
filings, not a quick seed step - end to end it takes several hours
(mostly the `fetch` download), so kick it off and let it run in the
background rather than expecting it inline with the rest of the
quickstart.

Then, inside Claude Code:

```
/plugin marketplace add ./marketplace
/plugin install grant-finder@grant-finder-dev
```

See [`plugin/README.md`](plugin/README.md) for the full local-development
and release workflow.

## License

[PolyForm Noncommercial 1.0.0](LICENSE).
