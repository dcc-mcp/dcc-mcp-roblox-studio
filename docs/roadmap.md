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

## Highest value

- Add a marketplace-backed Roblox gameplay skill with a tested asset workflow.
  The executable `neon-checkpoint-run` example now covers marketplace search,
  CC BY asset download, typed scene assembly, gameplay scripts, and live tree
  verification. Roblox-specific marketplace entries remain a future catalog
  addition because the current marketplace asset entries target other DCCs.

## Follow-up

- Add repository examples for script maintenance, scene assembly, and a
  cross-DCC handoff that combines native tools with the official namespace.

## Evidence

The neon checkpoint example is the first executable showcase workflow. Future
showcases should capture the request, the visible Studio result, and the
inspection response together so a screenshot has a clear relationship to the
operation it demonstrates.
