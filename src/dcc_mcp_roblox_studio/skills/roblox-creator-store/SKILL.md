---
name: roblox-creator-store
description: >-
  Roblox Creator Store asset workflow. Search the public Creator Store or a
  permitted Creator Inventory, inspect results and license metadata, then
  insert a selected numeric asset ID through Roblox Studio's official MCP
  namespace. Use when a scene needs authored Roblox assets.
license: MIT
compatibility: Roblox Studio with the built-in Studio MCP server enabled
allowed-tools: MCP
metadata:
  dcc-mcp:
    dcc: roblox-studio
    version: "0.1.0"
    layer: domain
    stage: asset_ingest
    search-hint: "Roblox Creator Store asset search insert model mesh audio material inventory"
    tags: "roblox, studio, creator-store, asset, search, insert"
    tools: tools.yaml
---

# Roblox Creator Store

Use the official compatibility tools returned by the connected Studio build.
The adapter keeps their current schemas under `roblox_official__*` so new
Studio releases can add asset types without a parallel adapter implementation.

## Workflow

1. Call `roblox_list_studios` and choose a `studio_id`.
2. Search the public Creator Store with `roblox_official__search_asset`.
3. Review the returned creator, asset type, price, tags, and numeric asset ID.
4. Insert one selected asset with `roblox_official__insert_asset`.
5. Inspect the inserted tree and run Play before saving.

For a Manhattan-style scene, search for free street props, traffic lights,
park props, and skyline materials. Keep the procedural blockout as the
playable baseline, then dress it with reviewed assets in small batches.

Asset permissions and script safety remain enforced by Roblox Studio. Do not
load arbitrary creator scripts or use runtime `InsertService:LoadAsset` in a
published game.
