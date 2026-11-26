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
        "roblox.get_class_schema",
        "roblox.scene_transaction",
        "dry_run",
        "roblox.create_instance",
        "roblox.modify_instance",
        "roblox.script_grep",
        "roblox.get_selection",
        "roblox.start_stop_play",
    ):
        assert method in source
    assert "task.spawn" in source
    assert 'return {action = "start", pending = true}' in source
    assert 'reason = "unpublished_local_place"' in source


def test_skill_package_contains_scene_authoring_contract() -> None:
    skill = ROOT / "src" / "dcc_mcp_roblox_studio" / "skills" / "roblox-scene-authoring"
    assert (skill / "SKILL.md").exists()
    assert "roblox_scene_transaction" in (skill / "tools.yaml").read_text(encoding="utf-8")
