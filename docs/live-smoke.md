# Live smoke test

## Prerequisites

- Roblox Studio is installed and a place is open.
- HTTP requests are enabled for the local plugin.
- Python 3.9 or newer is available.

## Steps

1. Install the adapter in a virtual environment with `pip install -e ".[dev]"`.
2. Start `dcc-mcp-roblox-studio --ws-port 9001`.
3. Copy `plugin/RobloxStudioDccMcpPlugin.rbxmx` into the Roblox Studio local
   Plugins folder and restart Studio.
4. Confirm the plugin connects to `ws://127.0.0.1:9001`.
5. Call `roblox_list_studios` and select a returned `studio_id`.
6. Call `roblox_get_studio_state`, `roblox_search_game_tree`, and
   `roblox_inspect_instance` against that ID.
7. Use `roblox_script_read` on a test script.
8. Use `roblox_multi_edit` on a disposable place and confirm one undo entry is
   created.

The PC8 validation used this flow with Studio PID `64692`, HWND `5183218`, and
the local bridge on port `9001`.
