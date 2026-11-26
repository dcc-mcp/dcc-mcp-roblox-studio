"""Stdio MCP server for the Roblox Studio DCC-MCP plugin bridge."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

from dcc_mcp_core import DccBridge

from dcc_mcp_roblox_studio.__version__ import __version__
from dcc_mcp_roblox_studio.audit import OperationAudit
from dcc_mcp_roblox_studio.official_mcp import OfficialMcpError, OfficialMcpProxy
from dcc_mcp_roblox_studio.schemas import get_class_schema
from dcc_mcp_roblox_studio.skill_catalog import describe_skill, search_skills

SERVER_NAME = "dcc-mcp-roblox-studio"


class RobloxDccBridge(DccBridge):
    """Keep Roblox session and lifecycle metadata across core API versions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._roblox_sessions: Dict[str, Dict[str, Any]] = {}
        self._roblox_events: List[Dict[str, Any]] = []

    async def _handle_hello(self, message: Dict[str, Any], websocket: Any) -> None:
        instance_id = str(message.get("instance_id") or message.get("peer_id") or "active")
        self._roblox_sessions[instance_id] = {
            "instance_id": instance_id,
            "studio_id": instance_id,
            "client": message.get("client"),
            "version": message.get("version"),
            "host_name": message.get("host_name"),
            "host_version": message.get("host_version"),
            "data_model_type": message.get("data_model_type"),
            "document": message.get("document"),
            "project": message.get("project"),
            "capabilities": message.get("capabilities", {}),
            "connected": True,
        }
        await super()._handle_hello(message, websocket)

    def _handle_event(self, message: Dict[str, Any]) -> None:
        data = message.get("data")
        event = dict(data) if isinstance(data, dict) else {"data": data}
        event.setdefault("event_type", message.get("event", "unknown"))
        event.setdefault("instance_id", message.get("instance_id"))
        self._roblox_events.append(event)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Return active sessions for both old and new dcc-mcp-core releases."""
        if self._roblox_sessions:
            return list(self._roblox_sessions.values())
        return (
            [
                {
                    "studio_id": "active",
                    "instance_id": "active",
                    "connected": self.is_connected(),
                }
            ]
            if self.is_connected()
            else []
        )

    def drain_events(self) -> List[Dict[str, Any]]:
        events = self._roblox_events
        self._roblox_events = []
        return events


def _tool(
    name: str,
    description: str,
    properties: Dict[str, Any],
    *,
    required: Optional[List[str]] = None,
    method: Optional[str] = None,
    read_only: bool = True,
    destructive: bool = False,
    idempotent: bool = False,
) -> Dict[str, Any]:
    """Create one MCP tool definition for the native bridge."""
    schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return {
        "name": name,
        "description": description,
        "inputSchema": schema,
        "annotations": {
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "idempotentHint": idempotent,
        },
        "method": method,
    }


_TARGET_PROPERTIES = {
    "studio_id": {"type": "string", "description": "Target Studio instance ID."},
    "instance_id": {"type": "string", "description": "Alias for studio_id."},
}

_DRY_RUN_PROPERTY = {
    "dry_run": {"type": "boolean", "default": False, "description": "Validate without changing Studio."}
}


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "roblox_list_studios",
        "description": "List connected Roblox Studio plugin sessions.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True, "idempotentHint": True},
        "method": None,
    },
    {
        **_tool(
            "roblox_get_studio_state",
            "Read the connected Roblox Studio state.",
            dict(_TARGET_PROPERTIES),
            method="roblox.get_studio_state",
            idempotent=True,
        ),
    },
    {
        **_tool(
            "roblox_search_game_tree",
            "Search the connected Studio data model by path, class, or name.",
            {
                "query": {"type": "string"},
                "root": {"type": "string", "default": "game"},
                "class_name": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
                **_TARGET_PROPERTIES,
            },
            required=["query"],
            method="roblox.search_game_tree",
            idempotent=True,
        ),
    },
    {
        **_tool(
            "roblox_inspect_instance",
            "Inspect one Roblox Studio instance and its immediate children.",
            {"path": {"type": "string"}, **_TARGET_PROPERTIES},
            required=["path"],
            method="roblox.inspect_instance",
            idempotent=True,
        ),
    },
    {
        **_tool(
            "roblox_script_read",
            "Read the source of a Script, LocalScript, or ModuleScript.",
            {"path": {"type": "string"}, **_TARGET_PROPERTIES},
            required=["path"],
            method="roblox.script_read",
            idempotent=True,
        ),
    },
    {
        **_tool(
            "roblox_multi_edit",
            "Apply bounded script edits as one ChangeHistoryService recording.",
            {
                "edits": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 32,
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "new_source": {"type": "string", "maxLength": 1000000},
                        },
                        "required": ["path", "new_source"],
                    },
                },
                **_TARGET_PROPERTIES,
            },
            required=["edits"],
            method="roblox.multi_edit",
            read_only=False,
            destructive=True,
        ),
    },
    _tool(
        "roblox_script_search",
        "Find scripts by name and class in the Studio data model.",
        {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
            **_TARGET_PROPERTIES,
        },
        required=["query"],
        method="roblox.script_search",
        idempotent=True,
    ),
    _tool(
        "roblox_script_grep",
        "Search script source across the Studio data model.",
        {
            "pattern": {"type": "string"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
            **_TARGET_PROPERTIES,
        },
        required=["pattern"],
        method="roblox.script_grep",
        idempotent=True,
    ),
    _tool(
        "roblox_create_instance",
        "Create an Instance under a parent with validated properties and attributes.",
        {
            "class_name": {"type": "string"},
            "parent": {"type": "string", "default": "game.Workspace"},
            "name": {"type": "string"},
            "properties": {"type": "object"},
            "attributes": {"type": "object"},
            **_DRY_RUN_PROPERTY,
            **_TARGET_PROPERTIES,
        },
        required=["class_name"],
        method="roblox.create_instance",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_modify_instance",
        "Modify properties and attributes on an existing Instance.",
        {
            "path": {"type": "string"},
            "properties": {"type": "object"},
            "attributes": {"type": "object"},
            **_DRY_RUN_PROPERTY,
            **_TARGET_PROPERTIES,
        },
        required=["path"],
        method="roblox.modify_instance",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_get_class_schema",
        "Return the supported property schema for a Roblox Instance class.",
        {"class_name": {"type": "string"}},
        required=["class_name"],
        idempotent=True,
    ),
    _tool(
        "roblox_scene_transaction",
        "Apply multiple scene operations as one undoable Studio transaction.",
        {
            "operations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["create", "modify", "delete", "clone", "move"],
                        },
                        "class_name": {"type": "string"},
                        "path": {"type": "string"},
                        "parent": {"type": "string"},
                        "name": {"type": "string"},
                        "properties": {"type": "object"},
                        "attributes": {"type": "object"},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["type"],
                },
            },
            **_TARGET_PROPERTIES,
        },
        required=["operations"],
        method="roblox.scene_transaction",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_delete_instance",
        "Delete an Instance with one ChangeHistoryService recording.",
        {"path": {"type": "string"}, **_DRY_RUN_PROPERTY, **_TARGET_PROPERTIES},
        required=["path"],
        method="roblox.delete_instance",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_clone_instance",
        "Clone an Instance into a new parent with one undoable operation.",
        {
            "path": {"type": "string"},
            "parent": {"type": "string"},
            "name": {"type": "string"},
            **_DRY_RUN_PROPERTY,
            **_TARGET_PROPERTIES,
        },
        required=["path", "parent"],
        method="roblox.clone_instance",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_move_instance",
        "Move an Instance to a new parent with one undoable operation.",
        {"path": {"type": "string"}, "parent": {"type": "string"}, **_DRY_RUN_PROPERTY, **_TARGET_PROPERTIES},
        required=["path", "parent"],
        method="roblox.move_instance",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_get_selection",
        "Read the current Studio selection.",
        dict(_TARGET_PROPERTIES),
        method="roblox.get_selection",
        idempotent=True,
    ),
    _tool(
        "roblox_set_selection",
        "Set the current Studio selection.",
        {"paths": {"type": "array", "items": {"type": "string"}, "maxItems": 128}, **_TARGET_PROPERTIES},
        required=["paths"],
        method="roblox.set_selection",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_insert_service",
        "Ensure a Roblox service exists and return its path.",
        {"class_name": {"type": "string"}, **_TARGET_PROPERTIES},
        required=["class_name"],
        method="roblox.insert_service",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_undo",
        "Undo the latest plugin change in Studio.",
        dict(_TARGET_PROPERTIES),
        method="roblox.undo",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_redo",
        "Redo the latest plugin change in Studio.",
        dict(_TARGET_PROPERTIES),
        method="roblox.redo",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_get_console_output",
        "Read recent Studio output messages captured by the plugin.",
        {"max_lines": {"type": "integer", "minimum": 1, "maximum": 512}, **_TARGET_PROPERTIES},
        method="roblox.get_console_output",
        idempotent=True,
    ),
    _tool(
        "roblox_start_stop_play",
        "Start or stop Studio playtesting through StudioTestService.",
        {"action": {"type": "string", "enum": ["start", "stop"]}, **_TARGET_PROPERTIES},
        required=["action"],
        method="roblox.start_stop_play",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_save_place",
        "Save the open Roblox place through StudioService.",
        {"note": {"type": "string", "maxLength": 500}, **_TARGET_PROPERTIES},
        method="roblox.save_place",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_bridge_events",
        "Drain lifecycle events received from connected Studio plugins.",
        {
            "event_type": {"type": "string"},
            "instance_id": {"type": "string"},
            "match": {"type": "object"},
            "max_events": {"type": "integer", "minimum": 1, "maximum": 1000},
        },
        method=None,
        idempotent=True,
    ),
    _tool(
        "roblox_wait_for_event",
        "Wait for a matching Studio bridge event until a bounded timeout.",
        {
            "event_type": {"type": "string"},
            "instance_id": {"type": "string"},
            "match": {"type": "object"},
            "timeout_ms": {"type": "integer", "minimum": 1, "maximum": 30000, "default": 5000},
            "poll_ms": {"type": "integer", "minimum": 10, "maximum": 1000, "default": 50},
        },
        idempotent=True,
    ),
    _tool(
        "roblox_get_audit_log",
        "Read recent adapter operation audit entries with redacted parameters.",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 1000}},
        idempotent=True,
    ),
]


TOOLS.extend(
    [
        _tool(
            "search",
            "Search the Roblox adapter's skills and typed tools.",
            {
                "query": {"type": "string"},
                "kind": {"type": "string", "enum": ["skill", "tool", "all"], "default": "all"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            idempotent=True,
        ),
        _tool(
            "describe",
            "Describe one Roblox skill or typed tool by name.",
            {"tool_slug": {"type": "string"}},
            required=["tool_slug"],
            idempotent=True,
        ),
        _tool(
            "load_skill",
            "Load one bundled Roblox skill and return its typed tools.",
            {"skill_name": {"type": "string"}},
            required=["skill_name"],
        ),
        _tool(
            "call",
            "Call a typed Roblox tool discovered through the Skills interface.",
            {
                "tool_slug": {"type": "string"},
                "arguments": {"type": "object"},
            },
            required=["tool_slug"],
        ),
        _tool(
            "search_skills",
            "Compatibility alias for searching bundled Roblox skills.",
            {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            idempotent=True,
        ),
    ]
)


def mcp_response(request_id: Any, result: Any) -> Dict[str, Any]:
    """Build one JSON-RPC success response."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def mcp_error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    """Build one JSON-RPC error response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _take_studio_target(arguments: Dict[str, Any]) -> Optional[str]:
    """Resolve Roblox's public ``studio_id`` alias to core's instance ID."""
    instance_id = arguments.pop("instance_id", None)
    studio_id = arguments.pop("studio_id", None)
    if instance_id and studio_id and instance_id != studio_id:
        raise ValueError("instance_id and studio_id must identify the same Studio session")
    return studio_id or instance_id


def _studio_snapshots(bridge: DccBridge) -> List[Dict[str, Any]]:
    """Expose core session metadata with Roblox's public ``studio_id`` spelling."""
    list_sessions = getattr(bridge, "list_sessions", None)
    if list_sessions is None:
        if not bridge.is_connected():
            return []
        return [
            {
                "studio_id": "active",
                "instance_id": "active",
                "connected": True,
                "note": "The installed dcc-mcp-core exposes one active bridge session.",
            }
        ]
    snapshots = []
    for session in list_sessions():
        snapshot = dict(session)
        snapshot["studio_id"] = snapshot.get("instance_id")
        snapshots.append(snapshot)
    return snapshots


class EventBuffer:
    """Keep unmatched bridge events available for later filtered reads."""

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []

    def collect(self, bridge: DccBridge) -> None:
        self._events.extend(bridge.drain_events())

    def take(
        self,
        *,
        event_type: Optional[str] = None,
        instance_id: Optional[str] = None,
        match: Optional[Dict[str, Any]] = None,
        max_events: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        remaining: List[Dict[str, Any]] = []
        for event in self._events:
            if _event_matches(event, event_type, instance_id, match) and (
                max_events is None or len(selected) < max_events
            ):
                selected.append(event)
            else:
                remaining.append(event)
        self._events = remaining
        return selected

    async def wait(
        self,
        bridge: DccBridge,
        *,
        event_type: Optional[str],
        instance_id: Optional[str],
        match: Optional[Dict[str, Any]],
        timeout_ms: int,
        poll_ms: int,
    ) -> Dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
        while True:
            self.collect(bridge)
            events = self.take(event_type=event_type, instance_id=instance_id, match=match, max_events=1)
            if events:
                return {"matched": True, "timed_out": False, "event": events[0]}
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return {"matched": False, "timed_out": True, "event": None}
            await asyncio.sleep(min(poll_ms / 1000, remaining))


def _event_matches(
    event: Dict[str, Any],
    event_type: Optional[str],
    instance_id: Optional[str],
    match: Optional[Dict[str, Any]],
) -> bool:
    """Match common lifecycle fields plus exact top-level fields."""
    if event_type and event_type not in {
        str(event.get("type", "")),
        str(event.get("event", "")),
        str(event.get("event_type", "")),
        str(event.get("state", "")),
    }:
        return False
    if instance_id:
        session = event.get("session")
        event_instance_id = event.get("instance_id")
        if event_instance_id is None and isinstance(session, dict):
            event_instance_id = session.get("instance_id")
        if event_instance_id != instance_id:
            return False
    return all(event.get(key) == value for key, value in (match or {}).items())


def _native_tool(tool_name: str) -> Optional[Dict[str, Any]]:
    """Return a native tool definition while excluding Skills management tools."""
    return next(
        (
            tool
            for tool in TOOLS
            if tool["name"] == tool_name
            and tool_name not in {"search", "describe", "load_skill", "call", "search_skills"}
        ),
        None,
    )


def _search_catalog(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Search bundled Skills and native typed tools."""
    query = str(arguments.get("query", "")).strip().lower()
    kind = str(arguments.get("kind", "all"))
    limit = max(1, min(int(arguments.get("limit", 20)), 100))
    skills = search_skills(query, limit)["skills"] if kind in {"all", "skill"} else []
    tools = []
    if kind in {"all", "tool"}:
        for tool in TOOLS:
            if _native_tool(tool["name"]) is None:
                continue
            haystack = f"{tool['name']} {tool['description']}".lower()
            if not query or query in haystack:
                tools.append(
                    {
                        "tool_slug": tool["name"],
                        "description": tool["description"],
                        "kind": "tool",
                    }
                )
            if len(tools) >= limit:
                break
    return {"skills": skills[:limit], "tools": tools[:limit], "count": len(skills[:limit]) + len(tools[:limit])}


def _describe_capability(tool_slug: str) -> Dict[str, Any]:
    """Describe a bundled skill or a native typed tool."""
    if tool_slug in {"roblox-scene-authoring", "roblox-creator-store"}:
        return describe_skill(tool_slug)
    tool = _native_tool(tool_slug)
    if tool is None:
        raise ValueError(f"tool or skill not found: {tool_slug}")
    return {key: value for key, value in tool.items() if key != "method"}


def _visible_tools(official: Optional[OfficialMcpProxy] = None) -> List[Dict[str, Any]]:
    """Build the native plus optional official tool surface."""
    visible = [{key: value for key, value in tool.items() if key != "method"} for tool in TOOLS]
    if official is None or not official.enabled:
        return visible
    try:
        visible.extend(official.list_tools())
    except (OfficialMcpError, OSError):
        # The native bridge remains usable when Studio's built-in server is
        # disabled, is not installed, or has a bad local launcher override.
        pass
    return visible


def _error_content(message: str) -> List[Dict[str, str]]:
    return [{"type": "text", "text": message}]


async def handle_mcp_message(
    bridge: DccBridge,
    message: Dict[str, Any],
    official: Optional[OfficialMcpProxy] = None,
    audit: Optional[OperationAudit] = None,
    event_buffer: Optional[EventBuffer] = None,
) -> None:
    """Handle one MCP JSON-RPC message on stdout."""
    audit = audit or OperationAudit()
    event_buffer = event_buffer or EventBuffer()
    request_id = message.get("id")
    if request_id is None:
        return

    method = message.get("method")
    if method == "initialize":
        result = {
            "protocolVersion": "2025-03-26",
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
            "capabilities": {"tools": {}},
        }
        print(json.dumps(mcp_response(request_id, result)), flush=True)
        return

    if method == "notifications/initialized":
        return

    if method == "tools/list":
        print(json.dumps(mcp_response(request_id, {"tools": _visible_tools(official)})), flush=True)
        return

    if method != "tools/call":
        print(json.dumps(mcp_error(request_id, -32601, f"Unknown MCP method: {method}")), flush=True)
        return

    params = message.get("params", {})
    tool_name = params.get("name")
    arguments = dict(params.get("arguments", {}))

    if tool_name == "search":
        result = _search_catalog(arguments)
        content = [{"type": "text", "text": json.dumps(result, sort_keys=True)}]
        print(json.dumps(mcp_response(request_id, {"content": content, "isError": False})), flush=True)
        return

    if tool_name == "search_skills":
        result = search_skills(arguments.get("query"), arguments.get("limit", 20))
        content = [{"type": "text", "text": json.dumps(result, sort_keys=True)}]
        print(json.dumps(mcp_response(request_id, {"content": content, "isError": False})), flush=True)
        return

    if tool_name == "describe":
        try:
            result = _describe_capability(str(arguments.get("tool_slug", "")))
            response = {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}], "isError": False}
        except Exception as exc:
            response = {"content": _error_content(str(exc)), "isError": True}
        print(json.dumps(mcp_response(request_id, response)), flush=True)
        return

    if tool_name == "load_skill":
        try:
            skill = describe_skill(str(arguments.get("skill_name", "")))
            result = {"loaded": True, "skill": skill["name"], "tools": skill["tools"]}
            response = {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}], "isError": False}
        except Exception as exc:
            response = {"content": _error_content(str(exc)), "isError": True}
        print(json.dumps(mcp_response(request_id, response)), flush=True)
        return

    if tool_name == "call":
        nested_name = str(arguments.get("tool_slug", ""))
        nested_tool = _native_tool(nested_name)
        if nested_tool is None and official is not None and nested_name.startswith(official.tool_prefix):
            try:
                result = official.call(nested_name, dict(arguments.get("arguments", {})))
                response = {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}], "isError": False}
            except Exception as exc:
                response = {"content": _error_content(str(exc)), "isError": True}
            print(json.dumps(mcp_response(request_id, response)), flush=True)
            return
        if nested_tool is None:
            print(json.dumps(mcp_error(request_id, -32601, f"Unknown typed tool: {nested_name}")), flush=True)
            return
        try:
            result = await _call_native_tool(
                bridge, nested_tool, dict(arguments.get("arguments", {})), audit, event_buffer
            )
            response = {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}], "isError": False}
        except Exception as exc:
            response = {"content": _error_content(str(exc)), "isError": True}
        print(json.dumps(mcp_response(request_id, response)), flush=True)
        return

    tool = next((item for item in TOOLS if item["name"] == tool_name), None)
    if (
        tool is None
        and official is not None
        and isinstance(tool_name, str)
        and tool_name.startswith(official.tool_prefix)
    ):
        try:
            result = official.call(tool_name, dict(params.get("arguments", {})))
            print(json.dumps(mcp_response(request_id, result)), flush=True)
        except Exception as exc:
            print(
                json.dumps(mcp_response(request_id, {"content": _error_content(str(exc)), "isError": True})), flush=True
            )
        return
    if tool is None:
        print(json.dumps(mcp_error(request_id, -32601, f"Unknown tool: {tool_name}")), flush=True)
        return

    try:
        result = await _call_native_tool(bridge, tool, arguments, audit, event_buffer)
        content = [{"type": "text", "text": json.dumps(result, sort_keys=True)}]
        print(json.dumps(mcp_response(request_id, {"content": content, "isError": False})), flush=True)
    except Exception as exc:
        print(json.dumps(mcp_response(request_id, {"content": _error_content(str(exc)), "isError": True})), flush=True)


_MUTATING_TOOLS = {
    "roblox_multi_edit",
    "roblox_create_instance",
    "roblox_modify_instance",
    "roblox_scene_transaction",
    "roblox_delete_instance",
    "roblox_clone_instance",
    "roblox_move_instance",
    "roblox_set_selection",
    "roblox_insert_service",
    "roblox_undo",
    "roblox_redo",
    "roblox_start_stop_play",
    "roblox_save_place",
}


async def _call_native_tool(
    bridge: DccBridge,
    tool: Dict[str, Any],
    arguments: Dict[str, Any],
    audit: OperationAudit,
    event_buffer: EventBuffer,
) -> Any:
    """Execute one native tool and record its operation audit entry."""
    tool_name = tool["name"]
    operation_id, started_at, started_iso = audit.begin(tool_name, dict(arguments))
    dry_run = bool(arguments.get("dry_run", False))
    try:
        result = await _call_native_tool_raw(bridge, tool, arguments, audit, event_buffer)
    except Exception as exc:
        audit.finish(
            operation_id,
            started_at,
            started_iso,
            tool_name,
            arguments,
            success=False,
            error=str(exc),
            dry_run=dry_run,
        )
        raise
    audit.finish(
        operation_id,
        started_at,
        started_iso,
        tool_name,
        arguments,
        success=True,
        result=result,
        dry_run=dry_run,
    )
    if tool_name in _MUTATING_TOOLS and isinstance(result, dict):
        result = dict(result)
        result["operation_id"] = operation_id
    return result


async def _call_native_tool_raw(
    bridge: DccBridge,
    tool: Dict[str, Any],
    arguments: Dict[str, Any],
    audit: OperationAudit,
    event_buffer: EventBuffer,
) -> Any:
    """Execute one native tool without audit wrapping."""
    tool_name = tool["name"]
    if tool_name == "roblox_list_studios":
        return {"studios": _studio_snapshots(bridge)}
    if tool_name == "roblox_get_class_schema":
        return get_class_schema(arguments["class_name"])
    if tool_name == "roblox_bridge_events":
        event_buffer.collect(bridge)
        return {
            "events": event_buffer.take(
                event_type=arguments.get("event_type"),
                instance_id=arguments.get("instance_id"),
                match=arguments.get("match"),
                max_events=arguments.get("max_events"),
            )
        }
    if tool_name == "roblox_wait_for_event":
        return await event_buffer.wait(
            bridge,
            event_type=arguments.get("event_type"),
            instance_id=arguments.get("instance_id"),
            match=arguments.get("match"),
            timeout_ms=max(1, min(int(arguments.get("timeout_ms", 5000)), 30000)),
            poll_ms=max(10, min(int(arguments.get("poll_ms", 50)), 1000)),
        )
    if tool_name == "roblox_get_audit_log":
        return {"entries": audit.entries(arguments.get("limit", 100))}
    target_instance_id = _take_studio_target(arguments)
    return await asyncio.to_thread(
        bridge.call,
        tool["method"],
        target_instance_id=target_instance_id,
        **arguments,
    )


class RobloxStudioMcpServer:
    """Composition root for the Roblox Studio stdio sidecar."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9001,
        *,
        enable_official_mcp: bool = False,
        official_mcp_command: Optional[str] = None,
    ) -> None:
        self.bridge = RobloxDccBridge(
            host=host,
            port=port,
            server_name=SERVER_NAME,
            server_version=__version__,
        )
        self.official = OfficialMcpProxy(command=official_mcp_command) if enable_official_mcp else None
        self.audit = OperationAudit()
        self.event_buffer = EventBuffer()

    @property
    def server_name(self) -> str:
        """Return the MCP server name used in the handshake."""
        return SERVER_NAME

    @property
    def version(self) -> str:
        """Return the adapter version."""
        return __version__

    def start(self) -> None:
        """Start the local plugin bridge."""
        self.bridge.connect()

    def stop(self) -> None:
        """Stop the local plugin bridge."""
        self.bridge.disconnect()
        if self.official is not None:
            self.official.close()

    async def run(self) -> None:
        """Start the bridge and serve MCP messages until stdin closes."""
        self.start()
        try:
            while True:
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    break
                try:
                    await handle_mcp_message(
                        self.bridge,
                        json.loads(line),
                        self.official,
                        self.audit,
                        self.event_buffer,
                    )
                except json.JSONDecodeError as exc:
                    print(json.dumps(mcp_error(None, -32700, str(exc))), flush=True)
        finally:
            self.stop()


def main() -> None:
    """Run the Roblox Studio MCP sidecar from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ws-port", type=int, default=9001)
    parser.add_argument(
        "--enable-official-mcp",
        action="store_true",
        help="Expose Roblox Studio's built-in MCP tools through the official compatibility route.",
    )
    parser.add_argument(
        "--official-mcp-command",
        default=None,
        help="Override the StudioMCP launcher path or command.",
    )
    args = parser.parse_args()
    asyncio.run(
        RobloxStudioMcpServer(
            host=args.host,
            port=args.ws_port,
            enable_official_mcp=args.enable_official_mcp,
            official_mcp_command=args.official_mcp_command,
        ).run()
    )


if __name__ == "__main__":
    main()
