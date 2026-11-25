# Create a visible scene checkpoint

This workflow turns an open place into a small, reviewable scene change. It
uses only native DCC-MCP tools, so it works without the official Roblox MCP
launcher.

## 1. Find the Studio session

Call `roblox_list_studios` and keep the returned `studio_id`.

```json
{
  "name": "roblox_list_studios",
  "arguments": {}
}
```

Use the selected ID in every call below. The examples use `studio-1` as a
placeholder.

## 2. Create the checkpoint

Create an anchored part in the open place. `Vector3` and `Color3` values are
decoded by the plugin before the properties are applied.

```json
{
  "name": "roblox_create_instance",
  "arguments": {
    "studio_id": "studio-1",
    "class_name": "Part",
    "parent": "game.Workspace",
    "name": "DccMcpCheckpoint",
    "properties": {
      "Anchored": true,
      "Size": {"type": "Vector3", "x": 12, "y": 1, "z": 12},
      "Position": {"type": "Vector3", "x": 0, "y": 0.5, "z": 0},
      "Color": {"type": "Color3", "r": 0.1, "g": 0.8, "b": 1.0}
    },
    "attributes": {
      "created_by": "dcc-mcp"
    }
  }
}
```

The result contains the created path, which should be
`game.Workspace.DccMcpCheckpoint`.

## 3. Inspect and select it

Read the object back and select it in Studio so the result is visible in the
editor.

```json
{
  "name": "roblox_inspect_instance",
  "arguments": {
    "studio_id": "studio-1",
    "path": "game.Workspace.DccMcpCheckpoint"
  }
}
```

```json
{
  "name": "roblox_set_selection",
  "arguments": {
    "studio_id": "studio-1",
    "paths": ["game.Workspace.DccMcpCheckpoint"]
  }
}
```

## 4. Make a safe follow-up edit

Change the color through the typed property route. The plugin records the
operation in Studio's change history.

```json
{
  "name": "roblox_modify_instance",
  "arguments": {
    "studio_id": "studio-1",
    "path": "game.Workspace.DccMcpCheckpoint",
    "properties": {
      "Color": {"type": "Color3", "r": 1.0, "g": 0.35, "b": 0.1}
    }
  }
}
```

Use `roblox_undo` to verify that the change is reversible, then inspect the
object again. Save the place only after reviewing the result.

```json
{
  "name": "roblox_undo",
  "arguments": {"studio_id": "studio-1"}
}
```

```json
{
  "name": "roblox_save_place",
  "arguments": {
    "studio_id": "studio-1",
    "note": "Reviewed DCC-MCP checkpoint"
  }
}
```

This sequence gives a useful first screenshot because it shows a concrete
scene object, its selected state, and a change that came from the MCP workflow.
