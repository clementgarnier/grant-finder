#!/usr/bin/env bash
# Fails if plugin/.mcp.json doesn't match plugin/mcp.config.release.json.
# Guards against accidentally committing the dev (localhost) MCP config -
# see plugin/README.md "Releasing".
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
committed="$repo_root/plugin/.mcp.json"
release="$repo_root/plugin/mcp.config.release.json"

if ! diff -q "$committed" "$release" >/dev/null 2>&1; then
  echo "error: plugin/.mcp.json does not match plugin/mcp.config.release.json" >&2
  echo "  Run: scripts/generate-plugin.sh release" >&2
  exit 1
fi
