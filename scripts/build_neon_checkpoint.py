"""Build and play-test the Neon Checkpoint Run in a local Roblox place."""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, List

from live_smoke import McpProcess, launch_studio


def vector3(x: float, y: float, z: float) -> Dict[str, Any]:
    return {"type": "Vector3", "x": x, "y": y, "z": z}


def color(r: float, g: float, b: float) -> Dict[str, Any]:
    return {"type": "Color3", "r": r, "g": g, "b": b}


def material(name: str) -> Dict[str, Any]:
    return {"type": "EnumItem", "enum": "Material", "name": name}


SERVER_SCRIPT = r"""local Players = game:GetService("Players")
local course = workspace:WaitForChild("NeonCheckpointRun")
local checkpoints = {
    course:WaitForChild("Checkpoint1"),
    course:WaitForChild("Checkpoint2"),
    course:WaitForChild("Checkpoint3"),
}
local hazards = {
    course:WaitForChild("LavaA"),
    course:WaitForChild("LavaB"),
}
local startPad = course:WaitForChild("StartPad")
local finishPad = course:WaitForChild("FinishPad")
local winsDebounce = {}

local function statsFor(player)
    local stats = player:FindFirstChild("leaderstats")
    if not stats then
        stats = Instance.new("Folder")
        stats.Name = "leaderstats"
        stats.Parent = player
        local stage = Instance.new("IntValue")
        stage.Name = "Stage"
        stage.Parent = stats
        local wins = Instance.new("IntValue")
        wins.Name = "Wins"
        wins.Parent = stats
    end
    return stats
end

local function teleportToStage(player, character)
    local stage = statsFor(player).Stage.Value
    local target = checkpoints[stage] or startPad
    character:PivotTo(target.CFrame + Vector3.new(0, 4, 0))
end

local function playerFromHit(hit)
    local character = hit and hit.Parent
    return character and Players:GetPlayerFromCharacter(character)
end

local function resetToCheckpoint(player)
    local character = player.Character
    if character then
        teleportToStage(player, character)
    end
end

for index, checkpoint in ipairs(checkpoints) do
    checkpoint.Touched:Connect(function(hit)
        local player = playerFromHit(hit)
        if player then
            local stage = statsFor(player).Stage
            stage.Value = math.max(stage.Value, index)
        end
    end)
end

for _, hazard in ipairs(hazards) do
    hazard.Touched:Connect(function(hit)
        local player = playerFromHit(hit)
        if player then
            resetToCheckpoint(player)
        end
    end)
end

finishPad.Touched:Connect(function(hit)
    local player = playerFromHit(hit)
    if player and not winsDebounce[player] then
        winsDebounce[player] = true
        local stats = statsFor(player)
        stats.Wins.Value += 1
        stats.Stage.Value = 0
        task.delay(1, function()
            winsDebounce[player] = nil
        end)
    end
end)

Players.PlayerAdded:Connect(function(player)
    statsFor(player)
    player.CharacterAdded:Connect(function(character)
        task.wait()
        teleportToStage(player, character)
    end)
end)
"""

HUD_SCRIPT = r"""local Players = game:GetService("Players")
local player = Players.LocalPlayer
local gui = Instance.new("ScreenGui")
gui.Name = "NeonCheckpointHUD"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")

local title = Instance.new("TextLabel")
title.Name = "Title"
title.Size = UDim2.new(0, 420, 0, 56)
title.Position = UDim2.new(0.5, -210, 0, 24)
title.BackgroundColor3 = Color3.fromRGB(10, 16, 36)
title.BackgroundTransparency = 0.15
title.TextColor3 = Color3.fromRGB(80, 240, 255)
title.Font = Enum.Font.GothamBold
title.TextSize = 26
title.Text = "NEON CHECKPOINT RUN"
title.Parent = gui

local status = Instance.new("TextLabel")
status.Name = "Status"
status.Size = UDim2.new(0, 360, 0, 42)
status.Position = UDim2.new(0.5, -180, 0, 86)
status.BackgroundTransparency = 1
status.TextColor3 = Color3.fromRGB(255, 255, 255)
status.Font = Enum.Font.Gotham
status.TextSize = 18
status.Parent = gui

local stats = player:WaitForChild("leaderstats")
local stage = stats:WaitForChild("Stage")
local wins = stats:WaitForChild("Wins")
local function refresh()
    status.Text = string.format("CHECKPOINT %d/3    WINS %d", stage.Value, wins.Value)
end
stage.Changed:Connect(refresh)
wins.Changed:Connect(refresh)
refresh()
"""


def operation(class_name: str, name: str, parent: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "create", "class_name": class_name, "name": name, "parent": parent, "properties": properties}


def build_operations() -> List[Dict[str, Any]]:
    course = "game.Workspace.NeonCheckpointRun"
    operations = [
        operation("Folder", "NeonCheckpointRun", "game.Workspace", {}),
        operation(
            "SpawnLocation",
            "StartPad",
            course,
            {
                "Anchored": True,
                "Size": vector3(14, 1, 14),
                "Position": vector3(0, 0.5, 0),
                "Color": color(0.1, 0.7, 1),
                "Material": material("Neon"),
            },
        ),
    ]
    pads = [
        ("Checkpoint1", (0, 3, 32), (0.2, 1, 0.8)),
        ("Checkpoint2", (14, 6, 64), (0.7, 0.2, 1)),
        ("Checkpoint3", (-12, 9, 92), (0.2, 1, 0.7)),
        ("FinishPad", (0, 12, 124), (1, 0.2, 0.7)),
    ]
    for name, position, tint in pads:
        operations.append(
            operation(
                "Part",
                name,
                course,
                {
                    "Anchored": True,
                    "Size": vector3(12, 1, 12),
                    "Position": vector3(*position),
                    "Color": color(*tint),
                    "Material": material("Neon"),
                },
            )
        )
    bridges = [
        ("Bridge1", (0, 1, 16), (10, 1, 24)),
        ("Bridge2", (7, 4, 48), (10, 1, 20)),
        ("Bridge3", (1, 7.5, 78), (10, 1, 20)),
    ]
    for name, position, size in bridges:
        operations.append(
            operation(
                "Part",
                name,
                course,
                {
                    "Anchored": True,
                    "Size": vector3(*size),
                    "Position": vector3(*position),
                    "Color": color(0.08, 0.12, 0.3),
                    "Material": material("Metal"),
                },
            )
        )
    for name, position in [("LavaA", (0, -1, 52)), ("LavaB", (0, -1, 108))]:
        operations.append(
            operation(
                "Part",
                name,
                course,
                {
                    "Anchored": True,
                    "Size": vector3(18, 1, 10),
                    "Position": vector3(*position),
                    "Color": color(1, 0.08, 0.1),
                    "Material": material("Neon"),
                },
            )
        )
    operations.extend(
        [
            operation("Script", "NeonCheckpointGame", "game.ServerScriptService", {"Source": SERVER_SCRIPT}),
            operation(
                "LocalScript",
                "NeonCheckpointHUD",
                "game.StarterPlayer.StarterPlayerScripts",
                {"Source": HUD_SCRIPT},
            ),
        ]
    )
    return operations


def call_tool(client: McpProcess, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    result = client.call("tools/call", {"name": name, "arguments": arguments})
    if not isinstance(result, dict):
        raise RuntimeError(f"{name} returned an unexpected result: {result!r}")
    return result


def wait_for_studio(client: McpProcess) -> str:
    deadline = time.monotonic() + float(os.environ.get("DCC_MCP_ROBLOX_SMOKE_WAIT_SECS", "60"))
    while time.monotonic() < deadline:
        studios = call_tool(client, "roblox_list_studios", {}).get("studios", [])
        if studios:
            return str(studios[0]["studio_id"])
        time.sleep(0.25)
    raise RuntimeError("no Roblox Studio plugin connected before timeout")


def run(keep_studio: bool) -> None:
    client = McpProcess(int(os.environ.get("DCC_MCP_ROBLOX_SMOKE_PORT", "9001")))
    studio = None
    try:
        client.call(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "neon-builder", "version": "1"},
            },
        )
        studio = launch_studio(install=True)
        studio_id = wait_for_studio(client)
        schema = call_tool(client, "roblox_get_class_schema", {"class_name": "Part"})
        if schema.get("known") is not True:
            raise RuntimeError("Part schema is unavailable")
        all_operations = build_operations()
        call_tool(
            client,
            "roblox_create_instance",
            {"studio_id": studio_id, "class_name": "Folder", "name": "NeonCheckpointRun", "parent": "game.Workspace"},
        )
        operations = all_operations[1:]
        dry_run = call_tool(
            client, "roblox_scene_transaction", {"studio_id": studio_id, "dry_run": True, "operations": operations}
        )
        if dry_run.get("valid") is not True:
            raise RuntimeError(f"game transaction dry-run failed: {dry_run}")
        applied = call_tool(client, "roblox_scene_transaction", {"studio_id": studio_id, "operations": operations})
        searched = call_tool(client, "roblox_search_game_tree", {"studio_id": studio_id, "query": "NeonCheckpoint"})
        scripts = call_tool(client, "roblox_script_search", {"studio_id": studio_id, "query": "NeonCheckpoint"})
        call_tool(
            client, "roblox_set_selection", {"studio_id": studio_id, "paths": ["game.Workspace.NeonCheckpointRun"]}
        )
        print(
            json.dumps(
                {
                    "studio_id": studio_id,
                    "operations": len(operations),
                    "applied": applied,
                    "scene_matches": searched,
                    "script_matches": scripts,
                    "save": "use Studio Save to File for unpublished local places",
                },
                sort_keys=True,
            )
        )
        if not keep_studio:
            studio.terminate()
            studio.wait(timeout=10)
            studio = None
    finally:
        client.close()
        if studio is not None and not keep_studio:
            studio.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-studio", action="store_true", help="Keep Studio open for a UI Save to File step.")
    args = parser.parse_args()
    run(keep_studio=args.keep_studio)
