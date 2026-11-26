"""Offline validation for the independently playable Manhattan showcase."""

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


def test_manhattan_package_contains_playable_city_and_scripts() -> None:
    root = ElementTree.parse(ROOT / "artifacts" / "manhattan-dash.rbxlx").getroot()
    city = _find_item(root, "Folder", "ManhattanReplica")
    names = {_name(item) for item in city.iter("Item")}
    assert {"SpawnPad", "Checkpoint_1", "Checkpoint_2", "Checkpoint_3", "CentralParkBeacon"}.issubset(names)
    assert "EmpireSpire" in names
    assert sum(name.startswith("Building_") for name in names) == 15

    server = _find_item(root, "Script", "ManhattanDashGame")
    hud = _find_item(root, "LocalScript", "ManhattanDashHUD")
    server_source = server.find("Properties/ProtectedString[@name='Source']")
    hud_source = hud.find("Properties/ProtectedString[@name='Source']")
    assert server_source is not None and "CentralParkBeacon" in (server_source.text or "")
    assert hud_source is not None and "MANHATTAN DASH" in (hud_source.text or "")


def test_manhattan_packaging_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.rbxlx"
    second = tmp_path / "second.rbxlx"
    for output in (first, second):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "package_manhattan.py"), str(output)],
            check=True,
            cwd=ROOT,
        )
    assert first.read_bytes() == second.read_bytes()
