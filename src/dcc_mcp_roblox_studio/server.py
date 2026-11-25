"""Stdio MCP server for the Roblox Studio DCC-MCP plugin bridge."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

from dcc_mcp_core import DccBridge

from dcc_mcp_roblox_studio.__version__ import __version__
from dcc_mcp_roblox_studio.official_mcp import OfficialMcpError, OfficialMcpProxy

SERVER_NAME = "dcc-mcp-roblox-studio"


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
            **_TARGET_PROPERTIES,
        },
        required=["path"],
        method="roblox.modify_instance",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_delete_instance",
        "Delete an Instance with one ChangeHistoryService recording.",
        {"path": {"type": "string"}, **_TARGET_PROPERTIES},
        required=["path"],
        method="roblox.delete_instance",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_clone_instance",
        "Clone an Instance into a new parent with one undoable operation.",
        {"path": {"type": "string"}, "parent": {"type": "string"}, "name": {"type": "string"}, **_TARGET_PROPERTIES},
        required=["path", "parent"],
        method="roblox.clone_instance",
        read_only=False,
        destructive=True,
    ),
    _tool(
        "roblox_move_instance",
        "Move an Instance to a new parent with one undoable operation.",
        {"path": {"type": "string"}, "parent": {"type": "string"}, **_TARGET_PROPERTIES},
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
        "Start or stop Studio playtesting through StudioService.",
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
        {"max_events": {"type": "integer", "minimum": 1, "maximum": 1000}},
        method=None,
        idempotent=True,
    ),
]


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
    snapshots = []
    for session in bridge.list_sessions():
        snapshot = dict(session)
        snapshot["studio_id"] = snapshot.get("instance_id")
        snapshots.append(snapshot)
    return snapshots


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
) -> None:
    """Handle one MCP JSON-RPC message on stdout."""
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
        arguments = dict(params.get("arguments", {}))
        if tool_name == "roblox_list_studios":
            result = {"studios": _studio_snapshots(bridge)}
        elif tool_name == "roblox_bridge_events":
            result = {"events": bridge.drain_events(arguments.get("max_events"))}
        else:
            target_instance_id = _take_studio_target(arguments)
            result = await asyncio.to_thread(
                bridge.call,
                tool["method"],
                target_instance_id=target_instance_id,
                **arguments,
            )
        content = [{"type": "text", "text": json.dumps(result, sort_keys=True)}]
        print(json.dumps(mcp_response(request_id, {"content": content, "isError": False})), flush=True)
    except Exception as exc:
        print(json.dumps(mcp_response(request_id, {"content": _error_content(str(exc)), "isError": True})), flush=True)


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
        self.bridge = DccBridge(
            host=host,
            port=port,
            server_name=SERVER_NAME,
            server_version=__version__,
        )
        self.official = OfficialMcpProxy(command=official_mcp_command) if enable_official_mcp else None

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
                    await handle_mcp_message(self.bridge, json.loads(line), self.official)
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
