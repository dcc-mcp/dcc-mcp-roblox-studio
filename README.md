# dcc-mcp-roblox-studio

Roblox Studio adapter for the DCC-MCP ecosystem.

The adapter connects an MCP client to an open Roblox Studio session through a
local stdio sidecar and a Studio plugin WebSocket. The sidecar uses
`dcc-mcp-core` for bridge lifecycle and multi-instance routing. The plugin owns
typed Studio API operations and groups script edits in one Studio undo record.

## Install

The package will be published as `dcc-mcp-roblox-studio` after the first
release-please release is merged. It requires `dcc-mcp-core>=0.20.54,<0.21.0`.

```powershell
python -m pip install dcc-mcp-roblox-studio
```

For development:

```powershell
python -m pip install -e ".[dev]"
```

## Connect

Build the local plugin model:

```powershell
python plugin/build_plugin.py
```

Copy `plugin/RobloxStudioDccMcpPlugin.rbxmx` into the Roblox Studio local
Plugins folder, restart Studio, and enable HTTP requests in Studio.

Start the adapter:

```powershell
dcc-mcp-roblox-studio --ws-port 9001
```

MCP client configuration:

```json
{
  "mcpServers": {
    "dcc-mcp-roblox-studio": {
      "command": "dcc-mcp-roblox-studio",
      "args": ["--ws-port", "9001"]
    }
  }
}
```

Call `roblox_list_studios` first when several Studio sessions are running.
Pass its `studio_id` to subsequent tools.

## Tools

- `roblox_list_studios`
- `roblox_get_studio_state`
- `roblox_search_game_tree`
- `roblox_inspect_instance`
- `roblox_script_read`
- `roblox_multi_edit`

The initial tool surface keeps host operations typed and bounded. Arbitrary
Luau execution and native UI input are outside this adapter's default scope.

## Official Roblox MCP route

Roblox Studio also provides an official local stdio MCP server. The DCC-MCP
translator can expose it through the gateway:

```powershell
dcc-mcp-server translate `
  --stdio "`$env:LOCALAPPDATA\Roblox\mcp.bat" `
  --app-type roblox-studio `
  --expose-streamable-http true
```

Use the official route when its built-in tools are sufficient. Use this
adapter when DCC-MCP should own plugin lifecycle, typed bridge policy, event
handling, or multi-instance metadata.

## Development

```powershell
python -m ruff check src tests
python -m ruff format --check src tests
python -m pytest
python -m build
```

See [architecture](docs/architecture.md) and the [live smoke test](docs/live-smoke.md).

## License

MIT. Roblox and Roblox Studio are trademarks of Roblox Corporation.
