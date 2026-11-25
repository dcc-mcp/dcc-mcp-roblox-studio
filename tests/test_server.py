"""MCP protocol tests for the Roblox Studio adapter."""

from __future__ import annotations

import asyncio
import json

from dcc_mcp_roblox_studio.__version__ import __version__
from dcc_mcp_roblox_studio.server import RobloxStudioMcpServer, handle_mcp_message


class FakeBridge:
    def list_sessions(self):
        return [{"instance_id": "studio-1", "ready": True}]

    def call(self, method, *, target_instance_id=None, **params):
        return {
            "method": method,
            "target_instance_id": target_instance_id,
            "params": params,
        }


def test_server_composition_root_uses_core_bridge() -> None:
    server = RobloxStudioMcpServer()
    assert server.server_name == "dcc-mcp-roblox-studio"
    assert server.version == __version__


def test_initialize_and_tools_list(capsys) -> None:
    bridge = FakeBridge()

    asyncio.run(handle_mcp_message(bridge, {"jsonrpc": "2.0", "id": 1, "method": "initialize"}))
    initialized = json.loads(capsys.readouterr().out)
    assert initialized["result"]["serverInfo"]["name"] == "dcc-mcp-roblox-studio"

    asyncio.run(handle_mcp_message(bridge, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
    listed = json.loads(capsys.readouterr().out)
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert {
        "roblox_list_studios",
        "roblox_multi_edit",
        "roblox_create_instance",
        "roblox_script_grep",
    }.issubset(names)


def test_tools_call_maps_studio_id_to_core_instance_id(capsys) -> None:
    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "roblox_get_studio_state",
                    "arguments": {"studio_id": "studio-1"},
                },
            },
        )
    )
    response = json.loads(capsys.readouterr().out)
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload == {
        "method": "roblox.get_studio_state",
        "target_instance_id": "studio-1",
        "params": {},
    }
