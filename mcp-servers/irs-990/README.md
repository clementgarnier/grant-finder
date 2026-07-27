# irs990-filings-grants connector

This connector's code is not duplicated under the plugin - it's the same
GraphQL-over-MCP server already used to research this project:

- `server.py` - the FastMCP + Strawberry GraphQL server (streamable-http
  transport)
- `requirements.txt` - its Python dependencies, installed by
  `../../docker/mcp/Dockerfile`
- `../../scripts/fetch_irs_990_files.py` / `../../scripts/build_mysql.py` -
  the pipeline that populates the MySQL database it reads from
- `../combined_server.py` - mounts this connector (alongside `grants-gov`)
  under one process, so both share a single deployed service; see that
  file's header comment
- `../../docker-compose.yml` - runs the `mysql` and `mcp` (both connectors)
  services together

## Running it locally

From the repo root:

```bash
docker compose up -d
```

This exposes the connector at `http://localhost:8000/irs-990/mcp`, bound
to `127.0.0.1` only. `plugin/mcp.config.dev.json` points at that address.

## Running it for the released plugin

`../../deploy/app.yaml` deploys this connector (alongside `grants-gov`, as
one App Platform service) to DigitalOcean, behind the hostname already set
in `plugin/mcp.config.release.json`. See that file's header comment for the
one-time managed-MySQL setup step and `doctl` deploy commands. After
deploying, regenerate `plugin/.mcp.json` with
`scripts/generate-plugin.sh release` before publishing.
