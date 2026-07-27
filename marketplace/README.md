# Grant Finder dev marketplace

Scaffold for the `grant-finder` marketplace entry, kept ready for the
public release described below. `.claude-plugin/marketplace.json`'s
`source` currently points at `../plugin` on disk as a placeholder.

That path won't actually resolve via `/plugin marketplace add`: Claude
Code requires relative plugin sources to stay under the marketplace root
(no `../`), so this directory can't be used to test the marketplace
install flow locally as-is. For local iteration on the plugin itself, see
the Cowork setup in `plugin/README.md` instead.

## For a public release

Once the plugin is ready to publish, either:

- swap `source` in `.claude-plugin/marketplace.json` from `"../plugin"` to
  a git reference (e.g. `{"source": "github", "repo":
  "clementgarnier/grant-finder", "path": "plugin"}` or a tagged URL), or
- copy this marketplace into its own repo pointing at the published
  plugin source.

Regenerate `plugin/.mcp.json` with `scripts/generate-plugin.sh release`
(see `plugin/README.md`) before tagging, so whatever the marketplace
points installers at has the hosted-endpoint config, not localhost.
