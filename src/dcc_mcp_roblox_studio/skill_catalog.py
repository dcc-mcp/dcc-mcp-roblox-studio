"""Built-in Skills metadata for the Roblox Studio adapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

SKILL_NAME = "roblox-scene-authoring"
SKILL_DESCRIPTION = (
    "Roblox Studio scene authoring skill for inspecting, creating, modifying, cloning, moving, "
    "deleting, selecting, and transactionally updating DataModel instances."
)

SKILL_TOOLS = [
    "roblox_get_class_schema",
    "roblox_search_game_tree",
    "roblox_inspect_instance",
    "roblox_create_instance",
    "roblox_modify_instance",
    "roblox_scene_transaction",
    "roblox_delete_instance",
    "roblox_clone_instance",
    "roblox_move_instance",
    "roblox_get_selection",
    "roblox_set_selection",
    "roblox_undo",
    "roblox_redo",
]


def skill_catalog() -> List[Dict[str, Any]]:
    """Return the adapter's built-in skill summaries."""
    return [
        {
            "name": SKILL_NAME,
            "description": SKILL_DESCRIPTION,
            "dcc": "roblox-studio",
            "layer": "domain",
            "stage": "authoring",
            "tools": list(SKILL_TOOLS),
        }
    ]


def search_skills(query: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """Search bundled skills and return progressive-loading metadata."""
    needle = str(query or "").strip().lower()
    matches = [
        skill
        for skill in skill_catalog()
        if not needle or needle in skill["name"].lower() or needle in skill["description"].lower()
    ]
    return {"skills": matches[: max(1, min(limit, 100))], "count": min(len(matches), max(1, min(limit, 100)))}


def describe_skill(name: str) -> Dict[str, Any]:
    """Return one skill's full metadata."""
    for skill in skill_catalog():
        if skill["name"] == name:
            return skill
    raise ValueError(f"skill not found: {name}")
