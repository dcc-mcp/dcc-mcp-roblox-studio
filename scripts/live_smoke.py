"""Run an MCP smoke test against Roblox Studio."""

from __future__ import annotations

import argparse
import json
import os
import shutil
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
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.request_id = 0
        self.adapter_stderr = self.process.stderr

    def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.request_id += 1
        request = {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params}
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(self.diagnostics("adapter exited before returning an MCP response"))
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(self.diagnostics(f"invalid MCP response: {exc}")) from exc
        if "error" in response:
            raise RuntimeError(response["error"])
        result = response["result"]
        if result.get("isError"):
            message = result.get("content", [{"text": "unknown MCP error"}])[0]["text"]
            raise RuntimeError(message)
        return json.loads(result["content"][0]["text"]) if "content" in result else result

    def diagnostics(self, message: str) -> str:
        error_output = "adapter still running"
        if self.process.poll() is not None and self.adapter_stderr:
            error_output = self.adapter_stderr.read()
        return json.dumps(
            {
                "message": message,
                "returncode": self.process.poll(),
                "adapter_stderr": error_output[-4000:],
            },
            sort_keys=True,
        )

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        self.process.terminate()
        self.process.wait(timeout=10)


def locate_studio() -> Path:
    configured = os.environ.get("ROBLOX_STUDIO_EXE")
    if configured:
        executable = Path(configured).expanduser()
        if executable.is_file():
            return executable
        raise RuntimeError(f"ROBLOX_STUDIO_EXE does not exist: {executable}")
    if os.name != "nt":
        raise RuntimeError("automatic Studio launch is supported on Windows only")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is unavailable, set ROBLOX_STUDIO_EXE")
    versions = Path(local_app_data) / "Roblox" / "Versions"
    candidates = sorted(versions.glob("*/RobloxStudioBeta.exe"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise RuntimeError(f"RobloxStudioBeta.exe was not found under {versions}")
    return candidates[-1]


def install_plugin() -> Path:
    if os.name != "nt":
        raise RuntimeError("automatic plugin installation is supported on Windows only")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is unavailable, cannot install the plugin")
    source = ROOT / "plugin" / "RobloxStudioDccMcpPlugin.rbxmx"
    target = Path(local_app_data) / "Roblox" / "Plugins" / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def launch_studio(install: bool) -> subprocess.Popen[str]:
    plugin_path = install_plugin() if install else None
    executable = locate_studio()
    place = os.environ.get("ROBLOX_STUDIO_PLACE")
    arguments = [str(executable)]
    if place:
        arguments.append(str(Path(place).expanduser()))
    process = subprocess.Popen(arguments)
    print(
        json.dumps(
            {
                "auto_launch": True,
                "studio_pid": process.pid,
                "studio_exe": str(executable),
                "place": place,
                "plugin": str(plugin_path) if plugin_path else None,
            }
        ),
        file=sys.stderr,
    )
    return process


def run_checks(call: Any) -> Dict[str, Any]:
    """Run the shared smoke assertions against any MCP call implementation."""

    def check(stage: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return call(method, params)
        except Exception as exc:
            raise RuntimeError(f"smoke stage {stage!r} failed: {exc}") from exc

    check(
        "initialize",
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
        studios = check("studio discovery", "tools/call", {"name": "roblox_list_studios", "arguments": {}})["studios"]
        if not studios:
            time.sleep(0.25)
    if not studios:
        raise RuntimeError("smoke stage 'studio discovery' failed: no Roblox Studio plugin connected before timeout")
    studio_id = studios[0]["studio_id"]

    schema = check(
        "class schema", "tools/call", {"name": "roblox_get_class_schema", "arguments": {"class_name": "Part"}}
    )
    assert schema["known"] is True
    assert schema["properties"]["Size"]["type"] == "Vector3"

    dry_run = check(
        "transaction dry-run",
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
                        "properties": {"Anchored": True, "Size": {"type": "Vector3", "x": 2, "y": 1, "z": 2}},
                    }
                ],
            },
        },
    )
    assert dry_run["dry_run"] is True
    assert dry_run["valid"] is True

    play_started = check(
        "play start",
        "tools/call",
        {
            "name": "roblox_start_stop_play",
            "arguments": {"studio_id": studio_id, "action": "start"},
        },
    )
    assert play_started["action"] == "start"
    play_state = check(
        "play state",
        "tools/call",
        {
            "name": "roblox_get_studio_state",
            "arguments": {"studio_id": studio_id},
        },
    )
    assert play_state["is_running"] is True
    play_stopped = check(
        "play stop",
        "tools/call",
        {
            "name": "roblox_start_stop_play",
            "arguments": {"studio_id": studio_id, "action": "stop"},
        },
    )
    assert play_stopped["action"] == "stop"
    saved = check(
        "save place",
        "tools/call",
        {
            "name": "roblox_save_place",
            "arguments": {"studio_id": studio_id, "note": "automated smoke"},
        },
    )
    assert saved["saved"] is True

    skills = check("skill search", "tools/call", {"name": "search", "arguments": {"query": "scene"}})
    assert any(skill["name"] == "roblox-scene-authoring" for skill in skills["skills"])
    loaded = check(
        "skill load", "tools/call", {"name": "load_skill", "arguments": {"skill_name": "roblox-scene-authoring"}}
    )
    assert loaded["loaded"] is True

    event = check(
        "event wait",
        "tools/call",
        {
            "name": "roblox_wait_for_event",
            "arguments": {"event_type": "__dcc_mcp_smoke_never__", "timeout_ms": 50, "poll_ms": 10},
        },
    )
    assert event["matched"] is False
    audit = check("audit log", "tools/call", {"name": "roblox_get_audit_log", "arguments": {"limit": 20}})
    assert any(entry["tool"] == "roblox_scene_transaction" for entry in audit["entries"])
    return {
        "studio_id": studio_id,
        "checks": ["schema", "dry_run", "play", "save", "skills", "event_wait", "audit"],
    }


def run(auto_launch: bool = False, install: bool = False) -> None:
    port = int(os.environ.get("DCC_MCP_ROBLOX_SMOKE_PORT", "9001"))
    client = McpProcess(port)
    studio = None
    try:
        if auto_launch:
            studio = launch_studio(install)
        print(json.dumps(run_checks(client.call)))
    except Exception as exc:
        raise RuntimeError(client.diagnostics(str(exc))) from exc
    finally:
        client.close()
        if studio is not None and os.environ.get("DCC_MCP_ROBLOX_SMOKE_CLOSE_STUDIO") == "1":
            studio.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--launch-studio", action="store_true", help="Launch Roblox Studio when no plugin is connected."
    )
    parser.add_argument(
        "--install-plugin", action="store_true", help="Install the bundled plugin before launching Studio."
    )
    options = parser.parse_args()
    run(
        auto_launch=options.launch_studio or os.environ.get("DCC_MCP_ROBLOX_AUTO_LAUNCH") == "1",
        install=options.install_plugin,
    )
