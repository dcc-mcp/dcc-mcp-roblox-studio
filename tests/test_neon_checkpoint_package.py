"""Offline validation for the independently playable Neon Checkpoint place."""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _name(item: ElementTree.Element) -> str:
    properties = item.find("Properties")
    assert properties is not None
    value = properties.find("string[@name='Name']")
    assert value is not None
    return value.text or ""


def _find_item(root: ElementTree.Element, class_name: str, name: str) -> ElementTree.Element:
    for item in root.iter("Item"):
        if item.get("class") == class_name and _name(item) == name:
            return item
    raise AssertionError(f"missing {class_name} {name}")


def test_packaged_place_contains_the_playable_game() -> None:
    place = ROOT / "artifacts" / "neon-checkpoint-run.rbxlx"
    document = ElementTree.parse(place)
    assert document.getroot().tag == "roblox"

    course = _find_item(document.getroot(), "Folder", "NeonCheckpointRun")
    course_names = {_name(item) for item in course.findall("Item")}
    assert course_names == {
        "StartPad",
        "Checkpoint1",
        "Checkpoint2",
        "Checkpoint3",
        "Bridge1",
        "Bridge2",
        "Bridge3",
        "LavaA",
        "LavaB",
        "FinishPad",
    }

    server_script = _find_item(document.getroot(), "Script", "NeonCheckpointGame")
    hud_script = _find_item(document.getroot(), "LocalScript", "NeonCheckpointHUD")
    for script, marker in (
        (server_script, "hazard.Touched"),
        (hud_script, "NEON CHECKPOINT RUN"),
    ):
        properties = script.find("Properties")
        assert properties is not None
        source = properties.find("ProtectedString[@name='Source']")
        assert source is not None and marker in (source.text or "")
    server_source = server_script.find("Properties/ProtectedString[@name='Source']")
    assert server_source is not None and "leaderstats" in (server_source.text or "")


def test_package_script_can_build_from_a_minimal_local_template(tmp_path: Path) -> None:
    template = tmp_path / "template.rbxlx"
    output = tmp_path / "package.rbxlx"
    root = ElementTree.Element("roblox", version="4")
    for value in ("null", "nil"):
        ElementTree.SubElement(root, "External").text = value
    for class_name, name in (
        ("Workspace", "Workspace"),
        ("ServerScriptService", "ServerScriptService"),
        ("StarterPlayer", "StarterPlayer"),
    ):
        item = ElementTree.SubElement(root, "Item", attrib={"class": class_name, "referent": f"RBX-{name}"})
        properties = ElementTree.SubElement(item, "Properties")
        ElementTree.SubElement(properties, "string", name="Name").text = name
        if class_name == "StarterPlayer":
            scripts = ElementTree.SubElement(
                item, "Item", attrib={"class": "StarterPlayerScripts", "referent": "RBX-scripts"}
            )
            script_properties = ElementTree.SubElement(scripts, "Properties")
            ElementTree.SubElement(script_properties, "string", name="Name").text = "StarterPlayerScripts"
    ElementTree.ElementTree(root).write(template, encoding="utf-8", xml_declaration=True)

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "package_neon_checkpoint.py"), str(template), str(output)],
        check=True,
        cwd=ROOT,
    )
    second_output = tmp_path / "package-second.rbxlx"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "package_neon_checkpoint.py"), str(template), str(second_output)],
        check=True,
        cwd=ROOT,
    )
    assert output.read_bytes() == second_output.read_bytes()
    packaged = ElementTree.parse(output).getroot()
    assert _find_item(packaged, "Folder", "NeonCheckpointRun") is not None
    assert _find_item(packaged, "Script", "NeonCheckpointGame") is not None
    assert _find_item(packaged, "LocalScript", "NeonCheckpointHUD") is not None
