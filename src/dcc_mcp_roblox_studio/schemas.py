"""Static Roblox class property schemas used by the native adapter."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

_COMMON_PROPERTIES: Dict[str, Dict[str, Any]] = {
    "Name": {"type": "string", "description": "Instance name."},
    "Archivable": {"type": "boolean", "description": "Whether the instance can be cloned."},
}

_BASE_PART_PROPERTIES: Dict[str, Dict[str, Any]] = {
    "Anchored": {"type": "boolean"},
    "CanCollide": {"type": "boolean"},
    "CanQuery": {"type": "boolean"},
    "CanTouch": {"type": "boolean"},
    "CastShadow": {"type": "boolean"},
    "Color": {"type": "Color3"},
    "CFrame": {"type": "CFrame"},
    "Material": {"type": "EnumItem", "enum": "Material"},
    "Position": {"type": "Vector3"},
    "Reflectance": {"type": "number", "minimum": 0, "maximum": 1},
    "Size": {"type": "Vector3"},
    "Transparency": {"type": "number", "minimum": 0, "maximum": 1},
}

_CLASS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "Instance": {"inherits": [], "properties": _COMMON_PROPERTIES},
    "Folder": {"inherits": ["Instance"], "properties": {}},
    "Model": {
        "inherits": ["Instance"],
        "properties": {"PrimaryPart": {"type": "Instance", "class_name": "BasePart"}},
    },
    "BasePart": {"inherits": ["Instance"], "properties": _BASE_PART_PROPERTIES},
    "Part": {"inherits": ["BasePart"], "properties": {}},
    "SpawnLocation": {"inherits": ["Part"], "properties": {"Enabled": {"type": "boolean"}}},
    "Script": {"inherits": ["LuaSourceContainer"], "properties": {"Source": {"type": "string"}}},
    "LocalScript": {"inherits": ["LuaSourceContainer"], "properties": {"Source": {"type": "string"}}},
    "ModuleScript": {"inherits": ["LuaSourceContainer"], "properties": {"Source": {"type": "string"}}},
    "LuaSourceContainer": {"inherits": ["Instance"], "properties": {"Source": {"type": "string"}}},
}


def _merged_properties(class_name: str) -> Dict[str, Dict[str, Any]]:
    schema = _CLASS_SCHEMAS[class_name]
    properties: Dict[str, Dict[str, Any]] = {}
    for parent in schema["inherits"]:
        if parent in _CLASS_SCHEMAS:
            properties.update(_merged_properties(parent))
    properties.update(schema["properties"])
    return properties


def get_class_schema(class_name: str) -> Dict[str, Any]:
    """Return a JSON-serializable schema for one supported Roblox class."""
    normalized = str(class_name or "").strip()
    if normalized not in _CLASS_SCHEMAS:
        return {
            "class_name": normalized,
            "known": False,
            "inherits": [],
            "properties": {},
            "message": "No static schema is bundled for this class. Studio validation remains available.",
        }
    schema = _CLASS_SCHEMAS[normalized]
    return {
        "class_name": normalized,
        "known": True,
        "inherits": list(schema["inherits"]),
        "properties": deepcopy(_merged_properties(normalized)),
    }


def supported_class_names() -> List[str]:
    """Return the classes with a bundled property schema."""
    return sorted(_CLASS_SCHEMAS)
