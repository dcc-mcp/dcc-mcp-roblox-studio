# Live smoke test

For a repeatable read-only MCP verification, run the bundled smoke runner
after the adapter and plugin are connected:

```powershell
python scripts/live_smoke.py
```

The runner checks the real stdio MCP entry point, Studio discovery, the `Part`
schema, transaction dry-run validation, skills discovery and loading, bounded
event waiting, and audit entries. It creates no Studio instances.

CI runs the same checks against a protocol-level fake Studio plugin with
`python scripts/ci_smoke.py`. This validates adapter startup, WebSocket hello,
stdio MCP routing, and failure boundaries without requiring a desktop Studio
session. The live runner remains available for validating the real plugin.

## Prerequisites

- Roblox Studio is installed and a place is open.
- HTTP requests are enabled for the local plugin.
- Python 3.9 or newer is available.

## Steps

1. Install the adapter in a virtual environment with `pip install -e ".[dev]"`.
2. Start `dcc-mcp-roblox-studio --ws-port 9001 --enable-official-mcp`.
3. Copy `plugin/RobloxStudioDccMcpPlugin.rbxmx` into the Roblox Studio local
   Plugins folder and restart Studio.
4. Confirm the plugin connects to `ws://127.0.0.1:9001`.
5. Call `roblox_list_studios` and select a returned `studio_id`.
6. Call `roblox_get_studio_state`, `roblox_search_game_tree`, and
   `roblox_inspect_instance` against that ID.
7. Use `roblox_script_read` on a test script.
8. Use `roblox_create_instance` on a disposable place, then verify the result
   with `roblox_inspect_instance` and `roblox_search_game_tree`.
9. Call `roblox_get_class_schema` for `Part`, then use
   `roblox_scene_transaction` to create and modify disposable objects in one
   undo entry.
10. Use `roblox_multi_edit` on a disposable place and confirm one undo entry is
   created.
11. Call `search`, `describe`, `load_skill`, and `call` for
   `roblox-scene-authoring` and verify the same typed tool is reachable.
12. Call `roblox_scene_transaction` with `dry_run: true` and verify that the
   place is unchanged.
13. Call `roblox_bridge_events` with `event_type` and `instance_id`, then use
   `roblox_wait_for_event` with a short timeout.
14. Call `roblox_get_audit_log` and verify the mutating operation has an
   `operation_id` and redacted arguments.
15. If the official launcher is available, call one `roblox_official__*` tool
    returned by `tools/list` and verify its result through MCP.

For a visible end-to-end result, follow the
[neon checkpoint workflow](examples/neon-checkpoint.md). It produces a scene
object that can be inspected and selected in Studio after the MCP calls.
