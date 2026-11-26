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
