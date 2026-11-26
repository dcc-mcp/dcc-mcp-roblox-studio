"""Package the generated Neon Checkpoint Run as an independent local place."""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Optional, Tuple

from build_neon_checkpoint import HUD_SCRIPT, SERVER_SCRIPT


def referent(class_name: str, name: str) -> str:
    digest = hashlib.sha1(f"{class_name}:{name}".encode("utf-8")).hexdigest().upper()
    return "RBX" + digest[:32]


def properties(name: str, *, source: Optional[str] = None) -> ElementTree.Element:
    node = ElementTree.Element("Properties")
    ElementTree.SubElement(node, "string", name="Name").text = name
    if source is not None:
        ElementTree.SubElement(node, "ProtectedString", name="Source").text = source
    return node


def item(class_name: str, name: str, *, source: Optional[str] = None) -> ElementTree.Element:
    node = ElementTree.Element("Item", attrib={"class": class_name, "referent": referent(class_name, name)})
    node.append(properties(name, source=source))
    return node


def set_bool(props: ElementTree.Element, name: str, value: bool) -> None:
    ElementTree.SubElement(props, "bool", name=name).text = str(value).lower()


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
    name: str, position: Tuple[float, float, float], size: Tuple[float, float, float], color: int
) -> ElementTree.Element:
    node = item("Part", name)
    props = node.find("Properties")
    assert props is not None
    set_bool(props, "Anchored", True)
    ElementTree.SubElement(props, "Color3uint8", name="Color3uint8").text = str(color)
    set_cframe(props, position)
    set_vector3(props, "size", size)
    return node


def find_child(parent: ElementTree.Element, class_name: str, name: str) -> ElementTree.Element:
    for candidate in parent.findall("Item"):
        props = candidate.find("Properties")
        name_node = props.find("string[@name='Name']") if props is not None else None
        if candidate.get("class") == class_name and name_node is not None and name_node.text == name:
            return candidate
    raise ValueError(f"missing {class_name} {name}")


def append_game(root: ElementTree.Element) -> None:
    workspace = find_child(root, "Workspace", "Workspace")
    server_scripts = find_child(root, "ServerScriptService", "ServerScriptService")
    starter_player = find_child(root, "StarterPlayer", "StarterPlayer")
    starter_scripts = find_child(starter_player, "StarterPlayerScripts", "StarterPlayerScripts")

    course = item("Folder", "NeonCheckpointRun")
    course_props = course.find("Properties")
    assert course_props is not None
    course.append(part("StartPad", (0, 0.5, 0), (14, 1, 14), 4284702720))
    for name, position, tint in (
        ("Checkpoint1", (0, 3, 32), 4284506367),
        ("Checkpoint2", (14, 6, 64), 4286541055),
        ("Checkpoint3", (-12, 9, 92), 4284569330),
        ("FinishPad", (0, 12, 124), 4294937727),
    ):
        course.append(part(name, position, (12, 1, 12), tint))
    for name, position, size in (
        ("Bridge1", (0, 1, 16), (10, 1, 24)),
        ("Bridge2", (7, 4, 48), (10, 1, 20)),
        ("Bridge3", (1, 7.5, 78), (10, 1, 20)),
    ):
        course.append(part(name, position, size, 4280232448))
    for name, position in (("LavaA", (0, -1, 52)), ("LavaB", (0, -1, 108))):
        course.append(part(name, position, (18, 1, 10), 4294901760))
    workspace.append(course)
    server_scripts.append(item("Script", "NeonCheckpointGame", source=SERVER_SCRIPT))
    starter_scripts.append(item("LocalScript", "NeonCheckpointHUD", source=HUD_SCRIPT))


def package(source: Path, output: Path) -> None:
    root = ElementTree.parse(source).getroot()
    append_game(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="A local .rbxlx template place.")
    parser.add_argument("output", type=Path, help="The packaged .rbxlx destination.")
    args = parser.parse_args()
    package(args.source, args.output)
