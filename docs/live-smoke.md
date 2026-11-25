# Live smoke test

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
9. Use `roblox_multi_edit` on a disposable place and confirm one undo entry is
   created.
10. If the official launcher is available, call one `roblox_official__*` tool
    returned by `tools/list` and verify its result through MCP.

For a visible end-to-end result, follow the
[neon checkpoint workflow](examples/neon-checkpoint.md). It produces a scene
object that can be inspected and selected in Studio after the MCP calls.
