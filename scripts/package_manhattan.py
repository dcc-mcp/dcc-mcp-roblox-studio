"""Build a deterministic, independently playable Manhattan-style Roblox place."""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Iterable, Optional, Tuple

SERVER_SCRIPT = r"""local Players = game:GetService("Players")
local city = workspace:WaitForChild("ManhattanReplica")
local spawnPad = city:WaitForChild("SpawnPad")
local checkpoints = {
    city:WaitForChild("Checkpoint_1"),
    city:WaitForChild("Checkpoint_2"),
    city:WaitForChild("Checkpoint_3"),
}
local goal = city:WaitForChild("CentralParkBeacon")
local finishDebounce = {}

local function statsFor(player)
    local stats = player:FindFirstChild("leaderstats")
    if not stats then
        stats = Instance.new("Folder")
        stats.Name = "leaderstats"
        stats.Parent = player
        local blocks = Instance.new("IntValue")
        blocks.Name = "Blocks"
        blocks.Parent = stats
        local wins = Instance.new("IntValue")
        wins.Name = "Wins"
        wins.Parent = stats
    end
    return stats
end

local function teleportToProgress(player, character)
    local stage = statsFor(player).Blocks.Value
    local target = checkpoints[stage] or spawnPad
    character:PivotTo(target.CFrame + Vector3.new(0, 5, 0))
end

local function playerFromHit(hit)
    local character = hit and hit.Parent
    return character and Players:GetPlayerFromCharacter(character)
end

for index, checkpoint in ipairs(checkpoints) do
    checkpoint.Touched:Connect(function(hit)
        local player = playerFromHit(hit)
        if player then
            local stage = statsFor(player).Blocks
            stage.Value = math.max(stage.Value, index)
        end
    end)
end

goal.Touched:Connect(function(hit)
    local player = playerFromHit(hit)
    if player and not finishDebounce[player] then
        finishDebounce[player] = true
        local stats = statsFor(player)
        stats.Wins.Value += 1
        stats.Blocks.Value = 0
        task.delay(1, function()
            finishDebounce[player] = nil
        end)
    end
end)

Players.PlayerAdded:Connect(function(player)
    statsFor(player)
    player.CharacterAdded:Connect(function(character)
        task.wait()
        teleportToProgress(player, character)
    end)
end)
"""


HUD_SCRIPT = r"""local Players = game:GetService("Players")
local player = Players.LocalPlayer
local gui = Instance.new("ScreenGui")
gui.Name = "ManhattanDashHUD"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")

local title = Instance.new("TextLabel")
title.Name = "Title"
title.Size = UDim2.new(0, 540, 0, 58)
title.Position = UDim2.new(0.5, -270, 0, 22)
title.BackgroundColor3 = Color3.fromRGB(18, 27, 45)
title.BackgroundTransparency = 0.08
title.TextColor3 = Color3.fromRGB(255, 220, 120)
title.Font = Enum.Font.GothamBlack
title.TextSize = 28
title.Text = "MANHATTAN DASH"
title.Parent = gui

local status = Instance.new("TextLabel")
status.Name = "Status"
status.Size = UDim2.new(0, 520, 0, 42)
status.Position = UDim2.new(0.5, -260, 0, 84)
status.BackgroundTransparency = 1
status.TextColor3 = Color3.fromRGB(255, 255, 255)
status.Font = Enum.Font.Gotham
status.TextSize = 18
status.Parent = gui

local hint = Instance.new("TextLabel")
hint.Name = "Hint"
hint.Size = UDim2.new(0, 600, 0, 30)
hint.Position = UDim2.new(0.5, -300, 1, -48)
hint.BackgroundTransparency = 1
hint.TextColor3 = Color3.fromRGB(180, 210, 230)
hint.Font = Enum.Font.Gotham
hint.TextSize = 16
hint.Text = "Run north through Midtown, touch the beacons, reach Central Park."
hint.Parent = gui

local stats = player:WaitForChild("leaderstats")
local blocks = stats:WaitForChild("Blocks")
local wins = stats:WaitForChild("Wins")
local function refresh()
    status.Text = string.format("BLOCK %d/3    COMPLETIONS %d", blocks.Value, wins.Value)
end
blocks.Changed:Connect(refresh)
wins.Changed:Connect(refresh)
refresh()
"""


def referent(class_name: str, name: str) -> str:
    digest = hashlib.sha1(f"{class_name}:{name}".encode("utf-8")).hexdigest().upper()
    return "RBX" + digest[:32]


def item(class_name: str, name: str, *, source: Optional[str] = None) -> ElementTree.Element:
    node = ElementTree.Element("Item", attrib={"class": class_name, "referent": referent(class_name, name)})
    properties = ElementTree.SubElement(node, "Properties")
    ElementTree.SubElement(properties, "string", name="Name").text = name
    if source is not None:
        ElementTree.SubElement(properties, "ProtectedString", name="Source").text = source
    return node


def properties(node: ElementTree.Element) -> ElementTree.Element:
    result = node.find("Properties")
    if result is None:
        raise ValueError(f"missing properties for {node.get('class')}")
    return result


def set_bool(props: ElementTree.Element, name: str, value: bool) -> None:
    ElementTree.SubElement(props, "bool", name=name).text = str(value).lower()


def set_float(props: ElementTree.Element, name: str, value: float) -> None:
    ElementTree.SubElement(props, "float", name=name).text = str(value)


def set_uint8_color(props: ElementTree.Element, value: int) -> None:
    ElementTree.SubElement(props, "Color3uint8", name="Color3uint8").text = str(value)


def set_vector3(props: ElementTree.Element, name: str, value: Tuple[float, float, float]) -> None:
    node = ElementTree.SubElement(props, "Vector3", name=name)
    for axis, number in zip(("X", "Y", "Z"), value):
        ElementTree.SubElement(node, axis).text = str(number)


def set_cframe(props: ElementTree.Element, position: Tuple[float, float, float]) -> None:
    node = ElementTree.SubElement(props, "CoordinateFrame", name="CFrame")
    for axis, number in zip(("X", "Y", "Z"), position):
        ElementTree.SubElement(node, axis).text = str(number)
    for row in range(3):
        for column in range(3):
            ElementTree.SubElement(node, f"R{row}{column}").text = "1" if row == column else "0"


def part(
    name: str,
    position: Tuple[float, float, float],
    size: Tuple[float, float, float],
    color: int,
    *,
    transparency: Optional[float] = None,
    reflectance: Optional[float] = None,
) -> ElementTree.Element:
    node = item("Part", name)
    props = properties(node)
    set_bool(props, "Anchored", True)
    set_uint8_color(props, color)
    set_cframe(props, position)
    set_vector3(props, "size", size)
    if transparency is not None:
        set_float(props, "Transparency", transparency)
    if reflectance is not None:
        set_float(props, "Reflectance", reflectance)
    return node


def model(name: str, children: Iterable[ElementTree.Element]) -> ElementTree.Element:
    node = item("Model", name)
    for child in children:
        node.append(child)
    return node


def building(name: str, x: float, z: float, height: float, color: int) -> ElementTree.Element:
    parts = [
        part("Facade", (x, height / 2, z), (24, height, 24), color),
        part("Roof", (x, height + 1, z), (26, 2, 26), 4280755995),
        part("WindowBandA", (x, height * 0.34, z - 12.3), (18, 5, 0.4), 4286611711, reflectance=0.15),
        part("WindowBandB", (x, height * 0.68, z - 12.3), (18, 5, 0.4), 4286611711, reflectance=0.15),
        part("FireEscape", (x + 13, height * 0.45, z), (1, height * 0.35, 5), 4282464255),
        part("FireEscapeRail", (x + 13, height * 0.65, z), (1, 1, 8), 4282464255),
    ]
    return model(name, parts)


def make_template() -> ElementTree.Element:
    root = ElementTree.Element("roblox", version="4")
    for value in ("null", "nil"):
        ElementTree.SubElement(root, "External").text = value
    for class_name, name in (
        ("Workspace", "Workspace"),
        ("ServerScriptService", "ServerScriptService"),
        ("StarterPlayer", "StarterPlayer"),
    ):
        parent = item(class_name, name)
        if class_name == "StarterPlayer":
            parent.append(item("StarterPlayerScripts", "StarterPlayerScripts"))
        root.append(parent)
    return root


def find_child(parent: ElementTree.Element, class_name: str, name: str) -> ElementTree.Element:
    for candidate in parent.findall("Item"):
        if candidate.get("class") != class_name:
            continue
        name_node = candidate.find("Properties/string[@name='Name']")
        if name_node is not None and name_node.text == name:
            return candidate
    raise ValueError(f"missing {class_name} {name}")


def append_city(root: ElementTree.Element) -> None:
    workspace = find_child(root, "Workspace", "Workspace")
    server_scripts = find_child(root, "ServerScriptService", "ServerScriptService")
    starter_player = find_child(root, "StarterPlayer", "StarterPlayer")
    starter_scripts = find_child(starter_player, "StarterPlayerScripts", "StarterPlayerScripts")

    city_parts = [
        part("Ground", (0, -1, 0), (360, 2, 360), 4284506367),
        part("Broadway", (-4, 0, 175), (18, 1, 330), 4282007050),
        part("FifthAvenue", (74, 0, 0), (18, 1, 330), 4282007050),
        part("CrossTown", (0, 0, 0), (330, 1, 18), 4282007050),
        part("HudsonRiver", (-156, 0, 0), (18, 1, 330), 4281348863, reflectance=0.25),
        part("BrooklynBridge", (-112, 5, 0), (70, 1, 18), 4284040703),
        part("CentralPark", (25, 0, 88), (92, 1, 88), 4281151590),
        part("ParkLake", (25, 1, 88), (28, 1, 55), 4281931007, reflectance=0.2),
        part("SpawnPad", (0, 1, -138), (16, 1, 16), 4294927510, reflectance=0.15),
        part("Checkpoint_1", (0, 1, -62), (12, 1, 12), 4294915071, reflectance=0.2),
        part("Checkpoint_2", (0, 1, 12), (12, 1, 12), 4294942719, reflectance=0.2),
        part("Checkpoint_3", (0, 1, 52), (12, 1, 12), 4294934527, reflectance=0.2),
        part("CentralParkBeacon", (25, 3, 112), (16, 5, 16), 4294937727, reflectance=0.2),
    ]

    city = item("Folder", "ManhattanReplica")
    for city_part in city_parts:
        city.append(city_part)

    block_index = 0
    for z in (-112, -62, -12, 38, 138):
        for x in (-78, -42, 112):
            block_index += 1
            height = 26 + ((block_index * 17) % 62)
            city.append(building(f"Building_{block_index:02d}", x, z, height, 4283911039 + (block_index % 4) * 65793))

    city.append(
        model(
            "EmpireSpire",
            [
                part("Tower", (78, 80, 82), (34, 160, 34), 4283586138),
                part("ObservationDeck", (78, 164, 82), (52, 8, 52), 4286611711, reflectance=0.15),
                part("Antenna", (78, 196, 82), (4, 56, 4), 4294927510, reflectance=0.25),
                part("Crown", (78, 120, 82), (42, 6, 42), 4294927510, reflectance=0.25),
            ],
        )
    )

    for name, x, z in (
        ("BroadwayNorth", -4, -94),
        ("BroadwayMidtown", -4, -24),
        ("BroadwayCentralPark", -4, 48),
        ("FifthAvenueNorth", 74, -94),
        ("FifthAvenueMidtown", 74, -24),
    ):
        city.append(part(f"StreetSign_{name}", (x, 9, z), (1, 8, 1), 4294937727, reflectance=0.2))

    workspace.append(city)
    server_scripts.append(item("Script", "ManhattanDashGame", source=SERVER_SCRIPT))
    starter_scripts.append(item("LocalScript", "ManhattanDashHUD", source=HUD_SCRIPT))


def package(source: Optional[Path], output: Path) -> None:
    root = ElementTree.parse(source).getroot() if source else make_template()
    append_city(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="The packaged .rbxlx destination")
    parser.add_argument("--template", type=Path, help="Optional minimal .rbxlx template")
    args = parser.parse_args()
    package(args.template, args.output)
