# Manhattan Dash

Manhattan Dash is a standalone local Roblox place that demonstrates the full
adapter loop with a visible, playable result. It uses a deterministic typed
blockout with a street grid, Hudson River, bridge, Central Park, fire escapes,
street markers, an Empire Spire landmark, checkpoints, a finish beacon, a
server-side progression script, and a client HUD.

The package is available at
[`artifacts/manhattan-dash.rbxlx`](../../artifacts/manhattan-dash.rbxlx). Open
it directly in Roblox Studio and press Play. It runs without the adapter after
it has been packaged.

## Creator Store dressing pass

The bundled `roblox-creator-store` skill keeps Creator Store operations in the
official Roblox namespace. After enabling Studio as an MCP server, search for
free reviewed assets and insert selected IDs into the open place.

```json
{
  "studio_id": "<from roblox_list_studios>",
  "query": "street lamp",
  "scope": "creator_store",
  "asset_type": "model",
  "price": "free"
}
```

Call the payload above through `roblox_official__search_asset`, inspect the
creator and asset metadata, then call `roblox_official__insert_asset` with the
returned numeric ID. Repeat the same flow for traffic lights, park props, and
skyline details. The procedural city remains the playable baseline while
Creator Store assets provide a reviewed dressing layer.

Roblox Studio enforces the creator's permissions and the current account's
access. Keep inserted assets small and inspect their descendants before Play.

## Verification

The live smoke runner can open this package automatically on a Windows runner.

```powershell
$env:DCC_MCP_ROBLOX_DEFAULT_PACKAGE = "1"
$env:DCC_MCP_ROBLOX_PACKAGE = "manhattan-dash"
$env:DCC_MCP_ROBLOX_EXPECT_GAME = "ManhattanReplica"
$env:DCC_MCP_ROBLOX_EXPECT_SCRIPT_PREFIX = "ManhattanDash"
$env:DCC_MCP_ROBLOX_EXPECT_GAME_SCRIPT = "ManhattanDashGame"
$env:DCC_MCP_ROBLOX_EXPECT_HUD_SCRIPT = "ManhattanDashHUD"
python scripts/live_smoke.py --launch-studio --install-plugin
```

The smoke run validates the `Part` property schema, a transaction dry-run,
Play, Save, the packaged city, the Skills interface, event waiting, and the
operation audit log.
