# Architecture

The adapter uses a local stdio MCP sidecar and a Studio plugin WebSocket. The
published package targets the released `dcc-mcp-core` 0.20.x contract.

```text
MCP client
    │ stdio
    ▼
dcc-mcp-roblox-studio
    │ dcc-mcp-core DccBridge
    ▼
Roblox Studio plugin
    │ typed Luau operations
    ▼
Roblox DataModel
```

The sidecar owns MCP transport, request routing, lifecycle snapshots, event
collection, and instance selection. The Studio plugin owns the typed Roblox
Studio API calls and ChangeHistoryService transaction.

The native scene authoring surface publishes a static class property schema
through `roblox_get_class_schema`. Scene create, modify, clone, move, and
delete operations can be composed in `roblox_scene_transaction`, which performs
preflight validation and records the complete batch as one Studio undo step.

The adapter also exposes the DCC-MCP Skills entry points `search`, `describe`,
`load_skill`, and `call`. The bundled `roblox-scene-authoring` skill describes
the typed scene workflow and is packaged with the adapter.

Every Studio session advertises a stable `instance_id`. The MCP-facing
`studio_id` argument is an adapter alias for that core session identifier.

The official Roblox Studio MCP server remains available through
`dcc-mcp-server translate` when the built-in tool surface is sufficient. This
adapter is intended for DCC-MCP-owned lifecycle, typed tool policy, and bridge
metadata.
