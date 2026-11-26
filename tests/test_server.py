"""MCP protocol tests for the Roblox Studio adapter."""

from __future__ import annotations

import asyncio
import json

from dcc_mcp_roblox_studio.__version__ import __version__
from dcc_mcp_roblox_studio.audit import OperationAudit
from dcc_mcp_roblox_studio.server import EventBuffer, RobloxStudioMcpServer, handle_mcp_message


class FakeOfficial:
    enabled = True
    tool_prefix = "roblox_official__"

    def list_tools(self):
        return [
            {
                "name": "roblox_official__search_asset",
                "description": "Search assets",
                "inputSchema": {"type": "object"},
            }
        ]

    def call(self, name, arguments):
        return {"name": name, "arguments": arguments}

    def status(self, *, probe=False):
        return {"enabled": True, "ready": bool(probe), "tool_count": 1}


class FakeBridge:
    def __init__(self):
        self.events = []

    def list_sessions(self):
        return [{"instance_id": "studio-1", "ready": True}]

    def call(self, method, *, target_instance_id=None, **params):
        return {
            "method": method,
            "target_instance_id": target_instance_id,
            "params": params,
        }

    def drain_events(self, max_events=None):
        events = self.events if max_events is None else self.events[:max_events]
        self.events = self.events[len(events) :]
        return events


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
        "roblox_get_class_schema",
        "roblox_scene_transaction",
        "search",
        "describe",
        "load_skill",
        "call",
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


def test_class_schema_is_available_through_mcp(capsys) -> None:
    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "roblox_get_class_schema",
                    "arguments": {"class_name": "Part"},
                },
            },
        )
    )
    response = json.loads(capsys.readouterr().out)
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["known"] is True
    assert payload["properties"]["Size"]["type"] == "Vector3"


def test_skills_interface_discovers_and_describes_scene_authoring(capsys) -> None:
    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "scene"}},
            },
        )
    )
    search_response = json.loads(capsys.readouterr().out)
    search_payload = json.loads(search_response["result"]["content"][0]["text"])
    assert search_payload["skills"][0]["name"] == "roblox-scene-authoring"

    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "describe",
                    "arguments": {"tool_slug": "roblox-scene-authoring"},
                },
            },
        )
    )
    describe_response = json.loads(capsys.readouterr().out)
    describe_payload = json.loads(describe_response["result"]["content"][0]["text"])
    assert "roblox_scene_transaction" in describe_payload["tools"]

    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "load_skill",
                    "arguments": {"skill_name": "roblox-scene-authoring"},
                },
            },
        )
    )
    load_response = json.loads(capsys.readouterr().out)
    load_payload = json.loads(load_response["result"]["content"][0]["text"])
    assert load_payload["loaded"] is True


def test_skill_call_routes_to_native_tool(capsys) -> None:
    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "call",
                    "arguments": {
                        "tool_slug": "roblox_get_class_schema",
                        "arguments": {"class_name": "Folder"},
                    },
                },
            },
        )
    )
    response = json.loads(capsys.readouterr().out)
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["class_name"] == "Folder"


def test_creator_store_skill_is_discoverable_and_loadable(capsys) -> None:
    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "creator store"}},
            },
        )
    )
    search_response = json.loads(capsys.readouterr().out)
    search_payload = json.loads(search_response["result"]["content"][0]["text"])
    assert any(skill["name"] == "roblox-creator-store" for skill in search_payload["skills"])

    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "tools/call",
                "params": {"name": "load_skill", "arguments": {"skill_name": "roblox-creator-store"}},
            },
        )
    )
    load_response = json.loads(capsys.readouterr().out)
    load_payload = json.loads(load_response["result"]["content"][0]["text"])
    assert load_payload["loaded"] is True
    assert "roblox_official__search_asset" in load_payload["tools"]


def test_creator_store_skill_describes_and_routes_official_tool(capsys) -> None:
    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 15,
                "method": "tools/call",
                "params": {"name": "describe", "arguments": {"tool_slug": "roblox-creator-store"}},
            },
        )
    )
    describe_response = json.loads(capsys.readouterr().out)
    describe_payload = json.loads(describe_response["result"]["content"][0]["text"])
    assert describe_payload["name"] == "roblox-creator-store"

    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 16,
                "method": "tools/call",
                "params": {
                    "name": "call",
                    "arguments": {
                        "tool_slug": "roblox_official__search_asset",
                        "arguments": {"query": "street light", "scope": "creator_store"},
                    },
                },
            },
            FakeOfficial(),
        )
    )
    call_response = json.loads(capsys.readouterr().out)
    call_payload = json.loads(call_response["result"]["content"][0]["text"])
    assert call_payload["name"] == "roblox_official__search_asset"
    assert call_payload["arguments"]["scope"] == "creator_store"


def test_official_mcp_status_is_available_through_the_native_route(capsys) -> None:
    asyncio.run(
        handle_mcp_message(
            FakeBridge(),
            {
                "jsonrpc": "2.0",
                "id": 17,
                "method": "tools/call",
                "params": {
                    "name": "roblox_get_official_mcp_status",
                    "arguments": {"probe": True},
                },
            },
            FakeOfficial(),
        )
    )
    response = json.loads(capsys.readouterr().out)
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload == {"enabled": True, "ready": True, "tool_count": 1}


def test_event_filter_wait_and_audit_are_available(capsys) -> None:
    bridge = FakeBridge()
    bridge.events = [
        {"type": "ready", "instance_id": "studio-1"},
        {"type": "heartbeat", "instance_id": "studio-1", "sequence": 3},
    ]
    audit = OperationAudit()
    event_buffer = EventBuffer()

    asyncio.run(
        handle_mcp_message(
            bridge,
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "roblox_bridge_events",
                    "arguments": {"event_type": "heartbeat", "instance_id": "studio-1"},
                },
            },
            None,
            audit,
            event_buffer,
        )
    )
    response = json.loads(capsys.readouterr().out)
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["events"] == [{"type": "heartbeat", "instance_id": "studio-1", "sequence": 3}]

    asyncio.run(
        handle_mcp_message(
            bridge,
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {"name": "roblox_wait_for_event", "arguments": {"event_type": "ready"}},
            },
            None,
            audit,
            event_buffer,
        )
    )
    wait_response = json.loads(capsys.readouterr().out)
    wait_payload = json.loads(wait_response["result"]["content"][0]["text"])
    assert wait_payload["matched"] is True

    asyncio.run(
        handle_mcp_message(
            bridge,
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "roblox_scene_transaction",
                    "arguments": {"dry_run": True, "operations": [{"type": "create", "class_name": "Part"}]},
                },
            },
            None,
            audit,
            event_buffer,
        )
    )
    dry_run_response = json.loads(capsys.readouterr().out)
    dry_run_payload = json.loads(dry_run_response["result"]["content"][0]["text"])
    assert dry_run_payload["method"] == "roblox.scene_transaction"
    assert dry_run_payload["params"]["dry_run"] is True

    asyncio.run(
        handle_mcp_message(
            bridge,
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {"name": "roblox_get_audit_log", "arguments": {"limit": 10}},
            },
            None,
            audit,
            event_buffer,
        )
    )
    audit_response = json.loads(capsys.readouterr().out)
    audit_payload = json.loads(audit_response["result"]["content"][0]["text"])
    assert audit_payload["entries"]
    assert any(entry["tool"] == "roblox_scene_transaction" for entry in audit_payload["entries"])
