<!-- install-sop-version: 1 -->
# Install dcc-mcp-roblox-studio

This adapter connects an MCP client to a running Roblox Studio session through the DCC-MCP bridge plugin.

## Requirements

- Roblox Studio with local plugin loading enabled.
- Python 3.9 or newer.
- A local MCP client that can launch stdio servers.

## Install the adapter

```powershell
python -m pip install --upgrade dcc-mcp-roblox-studio
```

The package requires `dcc-mcp-core>=0.20.54,<0.21.0`.

## Install the Roblox Studio plugin

1. Run `python plugin/build_plugin.py` from a source checkout, or use the packaged `RobloxStudioDccMcpPlugin.rbxmx` file.
2. Copy `RobloxStudioDccMcpPlugin.rbxmx` into the Roblox Studio local Plugins folder.
3. Restart Roblox Studio and enable the `DCC-MCP Roblox Studio` plugin.
4. Enable HTTP requests in Roblox Studio when the plugin prompts for access.

The plugin opens the local bridge on port `9001` by default.

## Start the stdio server

```powershell
dcc-mcp-roblox-studio --ws-port 9001
```

Configure the MCP client with the stdio command:

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

Call `roblox_list_studios` first when multiple Studio sessions are running. Pass the returned `studio_id` to later tools.

## Verify the connection

Use the adapter's `roblox_list_studios` tool. A ready session reports its Studio identifier and bridge state. Follow with `roblox_get_studio_state` to verify the selected session.

## Troubleshooting

- Confirm the plugin is enabled in Roblox Studio.
- Confirm HTTP requests are enabled in Studio.
- Confirm the stdio server and Studio plugin use the same WebSocket port.
- Use `roblox_list_studios` to select the correct Studio instance when several sessions are open.

## Uninstall

```powershell
python -m pip uninstall dcc-mcp-roblox-studio dcc-mcp-core
```

Remove the `DCC-MCP Roblox Studio` plugin from the Roblox Studio local Plugins folder if it is no longer needed.
