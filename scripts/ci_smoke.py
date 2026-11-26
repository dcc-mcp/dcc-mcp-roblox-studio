"""Run the smoke checks against a protocol-level fake Studio plugin."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import websockets
from live_smoke import McpProcess, run_checks

ROOT = Path(__file__).parents[1]


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def fake_studio(websocket: Any) -> None:
    is_running = False
    await websocket.send(
        json.dumps(
            {
                "type": "hello",
                "client": "roblox-studio-plugin-ci",
                "version": "ci",
                "host_name": "Fake Roblox Studio",
                "host_version": "ci",
                "instance_id": "ci-studio-1",
                "document": "ci-place",
                "project": "ci-project",
                "capabilities": {"scene_transaction": True, "get_class_schema": True},
            }
        )
    )
    async for raw in websocket:
        message = json.loads(raw)
        if message.get("type") != "request":
            continue
        method = message.get("method")
        if method == "roblox.scene_transaction":
            result = {"dry_run": True, "valid": True, "action": "scene_transaction", "count": 1}
        elif method == "roblox.start_stop_play":
            is_running = message.get("params", {}).get("action") == "start"
            result = {"action": "start" if is_running else "stop"}
        elif method == "roblox.get_studio_state":
            result = {"name": "Fake Roblox Studio", "is_edit": not is_running, "is_running": is_running}
        elif method == "roblox.search_game_tree":
            result = {"results": [{"name": "ManhattanReplica", "path": "game.Workspace.ManhattanReplica"}]}
        elif method == "roblox.script_search":
            result = {
                "results": [
                    {"name": "ManhattanDashGame", "class_name": "Script"},
                    {"name": "ManhattanDashHUD", "class_name": "LocalScript"},
                ]
            }
        elif method == "roblox.save_place":
            result = {"saved": True, "note": message.get("params", {}).get("note")}
        else:
            result = {}
        await websocket.send(
            json.dumps(
                {
                    "type": "response",
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": result,
                }
            )
        )


def fake_official_command() -> tuple[tempfile.TemporaryDirectory[str], str]:
    """Build a tiny official-server fixture for CI compatibility coverage."""
    directory = tempfile.TemporaryDirectory(prefix="roblox-official-ci-")
    script = Path(directory.name) / "fake_official_mcp.py"
    script.write_text(
        """
import json
import sys

TOOLS = [
    {"name": "search_asset", "description": "Search Creator Store", "inputSchema": {"type": "object"}},
    {"name": "insert_asset", "description": "Insert Creator Store asset", "inputSchema": {"type": "object"}},
]

for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if method == "notifications/initialized":
        continue
    if method == "initialize":
        result = {"protocolVersion": "2025-03-26", "capabilities": {}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params", {})
        result = {
            "content": [{"type": "text", "text": json.dumps({"asset_id": 123, "params": params})}],
            "isError": False,
        }
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}), flush=True)
""",
        encoding="utf-8",
    )
    return directory, f"{sys.executable} {script}"


async def run() -> Dict[str, Any]:
    for key, value in {
        "DCC_MCP_ROBLOX_EXPECT_GAME": "ManhattanReplica",
        "DCC_MCP_ROBLOX_EXPECT_SCRIPT_PREFIX": "ManhattanDash",
        "DCC_MCP_ROBLOX_EXPECT_GAME_SCRIPT": "ManhattanDashGame",
        "DCC_MCP_ROBLOX_EXPECT_HUD_SCRIPT": "ManhattanDashHUD",
    }.items():
        os.environ.setdefault(key, value)
    port = free_port()
    official_directory, official_command = fake_official_command()
    old_environment = {
        key: os.environ.get(key) for key in ("DCC_MCP_ROBLOX_ENABLE_OFFICIAL", "DCC_MCP_ROBLOX_OFFICIAL_MCP")
    }
    os.environ["DCC_MCP_ROBLOX_ENABLE_OFFICIAL"] = "1"
    os.environ["DCC_MCP_ROBLOX_OFFICIAL_MCP"] = official_command
    adapter: Optional[McpProcess] = None
    plugin = None
    try:
        adapter = McpProcess(port, enable_official=True)
        for _ in range(30):
            try:
                plugin = await websockets.connect(f"ws://127.0.0.1:{port}")
                break
            except OSError:
                await asyncio.sleep(0.1)
        if plugin is None:
            raise RuntimeError("fake Studio could not connect to adapter")
        plugin_task = asyncio.create_task(fake_studio(plugin))
        try:
            assert adapter is not None
            return await asyncio.to_thread(run_checks, adapter.call)
        finally:
            plugin_task.cancel()
            await asyncio.gather(plugin_task, return_exceptions=True)
            await plugin.close()
    finally:
        if adapter is not None:
            adapter.close()
        official_directory.cleanup()
        for key, value in old_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run())))
