"""Tests for the official Roblox MCP compatibility proxy."""

from __future__ import annotations

import sys
from pathlib import Path

from dcc_mcp_roblox_studio.official_mcp import OfficialMcpProxy
from dcc_mcp_roblox_studio.server import _visible_tools


def test_official_proxy_discovers_and_forwards_tools(tmp_path: Path) -> None:
    script = tmp_path / "fake_official_mcp.py"
    script.write_text(
        """
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if method == "notifications/initialized":
        continue
    if method == "initialize":
        result = {"protocolVersion": "2025-03-26", "capabilities": {}}
    elif method == "tools/list":
        result = {"tools": [{"name": "official_ping", "description": "Ping Studio", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": json.dumps(request["params"])}], "isError": False}
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
""",
        encoding="utf-8",
    )

    proxy = OfficialMcpProxy(command=f"{sys.executable} {script}")
    try:
        tools = proxy.list_tools()
        assert tools[0]["name"] == "roblox_official__official_ping"
        status = proxy.status(probe=True)
        assert status["ready"] is True
        assert status["tool_names"] == ["roblox_official__official_ping"]
        result = proxy.call("roblox_official__official_ping", {"studio_id": "studio-1"})
        assert result["isError"] is False
        assert "studio-1" in result["content"][0]["text"]
    finally:
        proxy.close()


def test_native_tools_remain_available_when_launcher_override_is_invalid() -> None:
    proxy = OfficialMcpProxy(command="missing-roblox-studio-mcp")
    tools = _visible_tools(proxy)
    assert any(tool["name"] == "roblox_list_studios" for tool in tools)
