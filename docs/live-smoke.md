# Live smoke test

For a repeatable MCP verification, run the bundled smoke runner after the
adapter and plugin are connected:

```powershell
python scripts/live_smoke.py
```

The runner checks the real stdio MCP entry point, Studio discovery, the `Part`
schema, transaction dry-run validation, Play start and stop, Save, skills
discovery and loading, bounded event waiting, and audit entries. The transaction
probe remains dry-run, while Play and Save exercise the connected place.

On Windows, the runner can install the bundled plugin and launch Studio without
a manual connection:

```powershell
python scripts/live_smoke.py --launch-studio --install-plugin
```

Set `ROBLOX_STUDIO_PLACE` to open a specific local place. Set
`ROBLOX_STUDIO_EXE` when Studio is installed outside the standard Roblox path.
Set `DCC_MCP_ROBLOX_SMOKE_CLOSE_STUDIO=1` to close the process after the run.
The default bridge port is `9001`, which matches the bundled plugin. Set
`DCC_MCP_ROBLOX_SMOKE_PORT` only when the plugin bundle is changed to use the
same port.
The command reports the launch PID, executable, place, plugin path, failing
stage, adapter return code, and adapter stderr when startup or a capability
check fails.

CI runs the same checks against a protocol-level fake Studio plugin with
`python scripts/ci_smoke.py`. This validates adapter startup, WebSocket hello,
stdio MCP routing, and failure boundaries without requiring a desktop Studio
session. A separate `workflow_dispatch` workflow runs the live runner on a
self-hosted Windows runner labelled `roblox-studio`, where Studio can use an
interactive desktop. It uploads the smoke log on every run.

## Prerequisites

- Roblox Studio is installed and the runner has an interactive desktop.
- HTTP requests are enabled for the local plugin.
- Python 3.9 or newer is available.

## Steps

1. Install the adapter in a virtual environment with `pip install -e ".[dev]"`.
2. The automatic mode starts the adapter on port `9001`, installs the bundled
   plugin, and launches Studio with `--launch-studio --install-plugin`.
3. For manual mode, start `dcc-mcp-roblox-studio --ws-port 9001
   --enable-official-mcp`, then copy
   `plugin/RobloxStudioDccMcpPlugin.rbxmx` into the Roblox Studio local Plugins
   folder and restart Studio.
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
15. Set `DCC_MCP_ROBLOX_ENABLE_OFFICIAL=1` to start the installed official
    StudioMCP launcher alongside the adapter. The smoke then requires
    `roblox_official__search_asset`, searches the Creator Store, and verifies
    the result through the adapter's `call` route.

For a visible end-to-end result, follow the
[Manhattan Dash workflow](examples/manhattan-dash.md). It opens the complete
city package, validates Play and Save, and provides the Creator Store dressing
pass used by the showcase.
