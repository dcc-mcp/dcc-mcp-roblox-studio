# Build a playable checkpoint run

This example uses the Roblox adapter's typed scene tools to create a small
playable course. The course has three checkpoints, two hazard zones, a finish
pad, a server-side progression script, and a client HUD.

## Marketplace asset workflow

The `dcc-asset-game-icons` marketplace entry was installed with:

```powershell
dcc-mcp-cli marketplace install dcc-asset-game-icons --output json --non-interactive
```

The `game-icons-assets` skill was then searched for `flag` and downloaded the
`delapouite/flag-objective.svg` icon. It is kept as a visual HUD reference
because Roblox's native scene authoring route does not import SVG files. The
asset remains accompanied by its CC BY 3.0 attribution in
`docs/assets/game-icons`.

## Scene layout

Create a `NeonCheckpointRun` folder under `game.Workspace`, then create the
following anchored `Part` instances under it with typed `Vector3` and `Color3`
properties.

| Instance | Position | Purpose |
| --- | --- | --- |
| `StartPad` | `(0, 0, 0)` | Player start |
| `Checkpoint1` | `(0, 3, 32)` | First progression trigger |
| `Checkpoint2` | `(14, 6, 64)` | Second progression trigger |
| `FinishPad` | `(0, 9, 100)` | Win trigger |
| `LavaA`, `LavaB` | `(0, -1, 52)`, `(0, -1, 88)` | Hazard zones |

Add three bridge parts between the pads. The complete live run used nine
parts and two scripts, all created through MCP. `roblox_search_game_tree`
returned ten scene instances under the folder, while `roblox_script_search`
returned both `NeonCheckpointGame` and `NeonCheckpointHUD`.

## Gameplay scripts

Create `ServerScriptService.NeonCheckpointGame` with `roblox_create_instance`
and a typed `Source` property. The script creates `leaderstats.Stage` and
`leaderstats.Wins`, updates the stage when a checkpoint is touched, respawns a
player at the last checkpoint, and increments wins at the finish pad.

Create `StarterPlayer.StarterPlayerScripts.NeonCheckpointHUD` as a
`LocalScript`. It creates a `ScreenGui` with the title `NEON CHECKPOINT RUN`
and displays the current checkpoint and win count.

## Verification loop

1. Call `roblox_get_class_schema` for `Part` before composing property values.
2. Call `roblox_scene_transaction` with `dry_run: true` for the final batch.
3. Apply the scene transaction and inspect `game.Workspace.NeonCheckpointRun`.
4. Search the game tree and scripts to verify the visible scene and scripts.
5. Start Play mode through `roblox_start_stop_play` and inspect console output.
6. Call `roblox_get_audit_log` to retain operation IDs and redacted arguments.

If the installed Studio plugin predates `roblox_scene_transaction`, the same
course can be assembled with repeated `roblox_create_instance` calls. The
committed plugin package contains the transactional route.

## Standalone local package

The repository includes [`artifacts/neon-checkpoint-run.rbxlx`](../../artifacts/neon-checkpoint-run.rbxlx),
which opens as a local Roblox Studio place and can be played immediately. The
package contains the course geometry and both gameplay scripts, so it does not
require the MCP adapter at play time.

The native `roblox_save_place` route persists published places through Roblox's
`AssetService`. Roblox rejects `SavePlaceAsync` for a local place with
`PlaceId=0`, so live smoke reports `reason=unpublished_local_place` while the
checked-in `.rbxlx` file remains the local package output.
