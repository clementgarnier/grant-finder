#!/usr/bin/env bash
# Stamps plugin/.mcp.json from one of the committed templates, so the plugin
# can point at localhost during development or at hosted endpoints for a
# public release without hand-editing the file Claude Code actually reads.
#
# Usage: scripts/generate-plugin.sh dev|release
set -euo pipefail

env="${1:-}"
if [[ "$env" != "dev" && "$env" != "release" ]]; then
  echo "Usage: $0 dev|release" >&2
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="$repo_root/plugin/mcp.config.$env.json"
dest="$repo_root/plugin/.mcp.json"

cp "$src" "$dest"
echo "Wrote $dest from $(basename "$src")"
