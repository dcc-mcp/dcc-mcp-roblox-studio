# Neon Checkpoint Run

Open `neon-checkpoint-run.rbxlx` in Roblox Studio and press **Play**. The
course includes three checkpoints, two lava hazards, a finish pad, server-side
progress tracking, and a HUD showing the current stage and wins.

The place file is a local, independently playable `.rbxlx` package. It was
assembled from the adapter's typed scene transaction workflow and verified in
Roblox Studio through the native MCP bridge.

`roblox_save_place` can persist published places through Roblox's
`AssetService`. A local place with `PlaceId=0` cannot be saved through that API,
so the adapter returns `reason=unpublished_local_place` for that case. This
file is the local saved package for that workflow.

# Manhattan Dash

Open `manhattan-dash.rbxlx` in Roblox Studio and press **Play**. It contains a
playable Manhattan-style city blockout with roads, a river, bridge, Central
Park, skyline landmark, fire escapes, checkpoints, a finish beacon, server
progression, and a client HUD.

The package is independent of the adapter at play time. The Creator Store
dressing workflow is documented in `docs/examples/manhattan-dash.md`.
