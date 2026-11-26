"""Run the smoke checks against a protocol-level fake Studio plugin."""

from __future__ import annotations

import asyncio
import json
import os
import socket
from pathlib import Path
from typing import Any, Dict

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


async def run() -> Dict[str, Any]:
    for key, value in {
        "DCC_MCP_ROBLOX_EXPECT_GAME": "ManhattanReplica",
        "DCC_MCP_ROBLOX_EXPECT_SCRIPT_PREFIX": "ManhattanDash",
        "DCC_MCP_ROBLOX_EXPECT_GAME_SCRIPT": "ManhattanDashGame",
        "DCC_MCP_ROBLOX_EXPECT_HUD_SCRIPT": "ManhattanDashHUD",
    }.items():
        os.environ.setdefault(key, value)
    port = free_port()
    adapter = McpProcess(port)
    plugin = None
    try:
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
            return await asyncio.to_thread(run_checks, adapter.call)
        finally:
            plugin_task.cancel()
            await asyncio.gather(plugin_task, return_exceptions=True)
            await plugin.close()
    finally:
        adapter.close()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run())))
