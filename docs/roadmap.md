# Capability roadmap

The current adapter already covers discovery, multi-instance routing, typed
DataModel edits, script search, selection, play control, console capture, save,
and official MCP compatibility. The next improvements should make those
capabilities safer to compose and easier to verify in an agent workflow.

## Completed in this iteration

- Add a structured property schema for supported Roblox classes. The schema
  is queryable through `roblox_get_class_schema` and enforced by the plugin for
  bundled classes.
- Add a batch scene transaction for create, modify, move, clone, and delete.
  One request produces one undo record and returns a per-operation result.
- Add the `roblox-scene-authoring` skill package and the core `search`,
  `describe`, `load_skill`, and `call` entry points.
- Add filtered event reads and bounded event waits with unmatched-event
  retention.
- Add redacted operation audit entries with stable operation IDs.
- Add dry-run validation for scene edits and scene transactions.

## Completed in this iteration

- Add the `roblox-creator-store` skill. It discovers the live official
  `search_asset` and `insert_asset` tools through the adapter's compatibility
  namespace, so the installed Studio build remains the schema authority.
- Add the standalone `manhattan-dash.rbxlx` game. It covers procedural city
  blockout, gameplay scripts, Play, Save, package tree verification, and a
  Creator Store dressing pass.
- Make live smoke unattended after the runner's Studio MCP profile is prepared.
  The smoke now launches Studio, installs the plugin, selects the expected
  package, probes official readiness, and writes bounded failure diagnostics.
- Add `roblox_get_official_mcp_status` so agents and CI can inspect the
  installed launcher and live official tool surface through the same adapter.

## Follow-up

- Add repository examples for script maintenance and a cross-DCC handoff that
  combines native tools with the official namespace.
- Capture a stable Manhattan smoke artifact from a configured self-hosted
  Studio runner and publish the package and diagnostics from CI.

## Evidence

The neon checkpoint example is the first executable showcase workflow. Future
showcases should capture the request, the visible Studio result, and the
inspection response together so a screenshot has a clear relationship to the
operation it demonstrates.
