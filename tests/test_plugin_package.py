"""Packaging tests for the Roblox Studio plugin bundle."""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_plugin_model_is_valid_xml() -> None:
    model = ROOT / "plugin" / "RobloxStudioDccMcpPlugin.rbxmx"
    document = ElementTree.parse(model)
    assert document.getroot().tag == "roblox"
    assert "DCC-MCP Roblox Studio" in model.read_text(encoding="utf-8")


def test_plugin_source_contains_typed_operations() -> None:
    source = (ROOT / "plugin" / "RobloxStudioDccMcpPlugin.luau").read_text(encoding="utf-8")
    for method in (
        "roblox.get_studio_state",
        "roblox.search_game_tree",
        "roblox.inspect_instance",
        "roblox.script_read",
        "roblox.multi_edit",
        "roblox.create_instance",
        "roblox.modify_instance",
        "roblox.script_grep",
        "roblox.get_selection",
        "roblox.start_stop_play",
    ):
        assert method in source
