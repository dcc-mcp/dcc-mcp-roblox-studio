"""Run a read-only MCP smoke test against an already connected Roblox Studio."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).parents[1]


class McpProcess:
    def __init__(self, port: int) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-m", "dcc_mcp_roblox_studio.server", "--ws-port", str(port)],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.request_id = 0

    def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.request_id += 1
        request = {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params}
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        response = json.loads(self.process.stdout.readline())
        if "error" in response:
            raise RuntimeError(response["error"])
        result = response["result"]
        if result.get("isError"):
            message = result.get("content", [{"text": "unknown MCP error"}])[0]["text"]
            raise RuntimeError(message)
        return json.loads(result["content"][0]["text"]) if "content" in result else result

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        self.process.terminate()
        self.process.wait(timeout=10)


def run() -> None:
    port = int(os.environ.get("DCC_MCP_ROBLOX_SMOKE_PORT", "19091"))
    client = McpProcess(port)
    try:
        client.call(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "roblox-live-smoke", "version": "1"},
            },
        )
        deadline = time.monotonic() + float(os.environ.get("DCC_MCP_ROBLOX_SMOKE_WAIT_SECS", "15"))
        studios = []
        while not studios and time.monotonic() < deadline:
            studios = client.call("tools/call", {"name": "roblox_list_studios", "arguments": {}})["studios"]
            if not studios:
                time.sleep(0.25)
        if not studios:
            raise RuntimeError("No Roblox Studio plugin connected before the smoke-test timeout")
        studio_id = studios[0]["studio_id"]

        schema = client.call("tools/call", {"name": "roblox_get_class_schema", "arguments": {"class_name": "Part"}})
        assert schema["known"] is True
        assert schema["properties"]["Size"]["type"] == "Vector3"

        dry_run = client.call(
            "tools/call",
            {
                "name": "roblox_scene_transaction",
                "arguments": {
                    "studio_id": studio_id,
                    "dry_run": True,
                    "operations": [
                        {
                            "type": "create",
                            "class_name": "Part",
                            "parent": "game.Workspace",
                            "name": "DccMcpAutomatedProbe",
                            "properties": {
                                "Anchored": True,
                                "Size": {"type": "Vector3", "x": 2, "y": 1, "z": 2},
                            },
                        }
                    ],
                },
            },
        )
        assert dry_run["dry_run"] is True
        assert dry_run["valid"] is True

        skills = client.call("tools/call", {"name": "search", "arguments": {"query": "scene"}})
        assert any(skill["name"] == "roblox-scene-authoring" for skill in skills["skills"])
        loaded = client.call(
            "tools/call", {"name": "load_skill", "arguments": {"skill_name": "roblox-scene-authoring"}}
        )
        assert loaded["loaded"] is True

        event = client.call(
            "tools/call",
            {
                "name": "roblox_wait_for_event",
                "arguments": {"event_type": "__dcc_mcp_smoke_never__", "timeout_ms": 50, "poll_ms": 10},
            },
        )
        assert event["matched"] is False
        audit = client.call("tools/call", {"name": "roblox_get_audit_log", "arguments": {"limit": 20}})
        assert any(entry["tool"] == "roblox_scene_transaction" for entry in audit["entries"])

        print(json.dumps({"studio_id": studio_id, "checks": ["schema", "dry_run", "skills", "event_wait", "audit"]}))
    finally:
        client.close()


if __name__ == "__main__":
    run()
