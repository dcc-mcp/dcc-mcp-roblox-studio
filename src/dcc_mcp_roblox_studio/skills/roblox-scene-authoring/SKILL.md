---
name: roblox-scene-authoring
description: >-
  Domain skill - Roblox Studio scene authoring: inspect, create, modify, clone,
  move, delete, select, and transactionally update DataModel instances. Use
  when an agent needs a typed, undoable scene change in an open place. Not for
  arbitrary Luau execution or Studio UI input.
license: MIT
compatibility: Roblox Studio with the DCC-MCP Roblox Studio plugin
allowed-tools: MCP
metadata:
  dcc-mcp:
    dcc: roblox-studio
    version: "0.1.2"
    layer: domain
    stage: authoring
    search-hint: "roblox studio scene instance property schema transaction workspace selection"
    tags: "roblox, studio, scene, instance, transaction"
    tools: tools.yaml
---

# Roblox Scene Authoring

Use `roblox_get_class_schema` before writing unfamiliar properties. Use
`roblox_scene_transaction` when several scene changes belong to one reviewable
undo step. The transaction validates all existing paths and supported property
values before opening a Studio change recording.

## Workflow

1. Call `roblox_list_studios` and select a `studio_id`.
2. Inspect the target with `roblox_search_game_tree` or
   `roblox_inspect_instance`.
3. Read the class contract with `roblox_get_class_schema`.
4. Apply one or more changes with `roblox_scene_transaction`.
5. Inspect the result and use `roblox_undo` when review requires rollback.

## Safety boundary

Property values use typed JSON forms such as `Vector3`, `Color3`, `CFrame`, and
`EnumItem`. Unknown Roblox classes remain available, while Studio performs the
final validation for classes outside the bundled schema.
