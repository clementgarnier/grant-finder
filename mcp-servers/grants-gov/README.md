# grants-gov connector

GraphQL-over-MCP server (`server.py`, streamable-http transport) that wraps
the [Simpler Grants API](https://api.simpler.grants.gov) - the newer
replacement for legacy grants.gov search - behind the same kind of typed
GraphQL schema the `irs990-filings-grants` connector puts in front of its
MySQL data.

- `server.py` - the FastMCP + Strawberry GraphQL server
- `requirements.txt` - its Python dependencies, installed by
  `../../docker/mcp/Dockerfile`

## Requirements

- `SIMPLER_GRANTS_API_KEY` - required. Get one by logging into
  [Simpler.Grants.gov](https://simpler.grants.gov) with Login.gov, then
  going to the developer page ("Manage API Keys" > "Create API Key"). See
  https://wiki.simpler.grants.gov/product/api for details. The key is
  passed to the upstream API as the `X-API-Key` header - keep it on the
  deployed server, not handed out to individual plugin installers (see
  `../../plugin/mcp.config.release.json`).
- `SIMPLER_GRANTS_API_BASE_URL` - optional, defaults to
  `https://api.simpler.grants.gov`.

## Running it locally

With `SIMPLER_GRANTS_API_KEY` set in the repo-root `.env`, from the repo
root:

```bash
docker compose up -d
```

This builds from `../../docker/mcp/Dockerfile` (the `mcp` service in
`../../docker-compose.yml`, which runs both connectors alongside `mysql`)
and exposes this connector at `http://localhost:8000/grants-gov/mcp`,
bound to `127.0.0.1` only. `plugin/mcp.config.dev.json` points at that
address. See `../combined_server.py` for how the two connectors are
mounted together.

To run just this connector standalone without Docker (e.g. for quick
iteration on this server alone):

```bash
pip install -r mcp-servers/grants-gov/requirements.txt
export SIMPLER_GRANTS_API_KEY=...   # or set it in the repo-root .env
python3 mcp-servers/grants-gov/server.py   # serves on :8001/mcp by itself
```

## Running it for the released plugin

`../../deploy/app.yaml` deploys this connector (alongside `irs-990`, as one
App Platform service to avoid paying for two always-on instances) to
DigitalOcean, with `SIMPLER_GRANTS_API_KEY` set as a secret there - behind
the hostname already set in `plugin/mcp.config.release.json`. After
deploying, regenerate `plugin/.mcp.json` with
`scripts/generate-plugin.sh release` before publishing.
