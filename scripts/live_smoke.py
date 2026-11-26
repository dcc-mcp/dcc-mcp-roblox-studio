"""Run an MCP smoke test against Roblox Studio."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dcc_mcp_roblox_studio.official_mcp import official_environment_diagnostics

ROOT = Path(__file__).parents[1]


def redact(text: str) -> str:
    """Keep failure reports useful without copying credential-shaped values."""
    return re.sub(
        r"(?i)(token|secret|password|authorization|bearer)\s*[:=]\s*[^\s,;]+",
        r"\1=<redacted>",
        text,
    )


def diagnostic_directory() -> Path:
    """Return the configured directory for machine-readable smoke evidence."""
    configured = os.environ.get("DCC_MCP_ROBLOX_DIAGNOSTIC_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / ".live-smoke-diagnostics" / stamp


def recent_studio_logs(limit: int = 3) -> list[Dict[str, Any]]:
    """Collect bounded tails from the most recent Studio logs."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return []
    log_root = Path(local_app_data) / "Roblox" / "logs"
    entries: list[Dict[str, Any]] = []
    for path in sorted(log_root.glob("*_Studio_*_last.log"), key=lambda item: item.stat().st_mtime, reverse=True)[
        :limit
    ]:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            entries.append({"name": path.name, "error": str(exc)})
            continue
        entries.append({"name": path.name, "tail": redact("\n".join(lines[-80:]))})
    return entries


def process_snapshot() -> str:
    """Return a bounded process listing useful for CI failure diagnosis."""
    if os.name != "nt":
        return "process snapshot unavailable outside Windows"
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq RobloxStudioBeta.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"process snapshot failed: {exc}"
    return redact(result.stdout[-4000:])


class McpProcess:
    def __init__(self, port: int, *, enable_official: bool = False) -> None:
        command = [sys.executable, "-m", "dcc_mcp_roblox_studio.server", "--ws-port", str(port)]
        if enable_official:
            command.append("--enable-official-mcp")
        self.process = subprocess.Popen(
            command,
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
        self._stderr_lines: "deque[str]" = deque(maxlen=200)
        self._stderr_thread = threading.Thread(target=self._pump_stderr, daemon=True, name="roblox-smoke-stderr")
        self._stderr_thread.start()

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
        return json.dumps(
            {
                "message": message,
                "returncode": self.process.poll(),
                "adapter_stderr": redact("".join(self._stderr_lines)[-4000:]),
            },
            sort_keys=True,
        )

    def close(self) -> None:
        if self.process.stdin:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self._stderr_thread.join(timeout=1)

    def _pump_stderr(self) -> None:
        if self.adapter_stderr is None:
            return
        for line in self.adapter_stderr:
            self._stderr_lines.append(line)


def locate_studio() -> Path:
    configured = os.environ.get("ROBLOX_STUDIO_EXE")
    if configured:
        executable = Path(configured).expanduser()
        if executable.is_file():
            return executable
        raise RuntimeError(f"ROBLOX_STUDIO_EXE does not exist: {executable}")
    if os.name != "nt":
        raise RuntimeError("automatic Studio launch is supported on Windows only")
    version_roots = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        version_roots.append(Path(local_app_data) / "Roblox" / "Versions")
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        program_files = os.environ.get(variable)
        if program_files:
            version_roots.append(Path(program_files) / "Roblox" / "Versions")
    # GitHub Actions service accounts may not inherit the interactive user's
    # ProgramFiles variables. Keep the documented Windows install roots as a
    # deterministic fallback, including the path used by the self-hosted
    # roblox-studio runner.
    version_roots.extend(
        [
            Path(r"C:\Program Files\Roblox\Versions"),
            Path(r"C:\Program Files (x86)\Roblox\Versions"),
        ]
    )
    candidates = sorted(
        {
            candidate
            for versions in version_roots
            if versions.is_dir()
            for candidate in versions.glob("*/RobloxStudioBeta.exe")
            if candidate.is_file()
        },
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        locations = ", ".join(str(root) for root in version_roots)
        raise RuntimeError(f"RobloxStudioBeta.exe was not found under {locations}")
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
    if not place and os.environ.get("DCC_MCP_ROBLOX_DEFAULT_PACKAGE") == "1":
        package_name = os.environ.get("DCC_MCP_ROBLOX_PACKAGE", "neon-checkpoint-run")
        package = ROOT / "artifacts" / f"{package_name}.rbxlx"
        if package.is_file():
            place = str(package)
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


def configure_automatic_showcase_defaults(auto_launch: bool) -> None:
    """Make the one-command runner exercise the checked-in playable package."""
    if not auto_launch:
        return
    defaults = {
        "DCC_MCP_ROBLOX_DEFAULT_PACKAGE": "1",
        "DCC_MCP_ROBLOX_PACKAGE": "manhattan-dash",
        "DCC_MCP_ROBLOX_EXPECT_GAME": "ManhattanReplica",
        "DCC_MCP_ROBLOX_EXPECT_SCRIPT_PREFIX": "ManhattanDash",
        "DCC_MCP_ROBLOX_EXPECT_GAME_SCRIPT": "ManhattanDashGame",
        "DCC_MCP_ROBLOX_EXPECT_HUD_SCRIPT": "ManhattanDashHUD",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def write_diagnostics(
    message: str,
    *,
    client: McpProcess,
    studio: Optional[subprocess.Popen[str]],
    auto_launch: bool,
    install: bool,
    official_enabled: bool,
) -> Path:
    """Persist bounded failure context so CI failures can be diagnosed offline."""
    directory = diagnostic_directory()
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "message": redact(message),
        "auto_launch": auto_launch,
        "install_plugin": install,
        "adapter": json.loads(client.diagnostics(message)),
        "studio": {
            "pid": studio.pid if studio is not None else None,
            "returncode": studio.poll() if studio is not None else None,
        },
        "environment": {
            "studio_exe": os.environ.get("ROBLOX_STUDIO_EXE"),
            "studio_place": os.environ.get("ROBLOX_STUDIO_PLACE"),
            "official_enabled": official_enabled,
            "official_command": os.environ.get("DCC_MCP_ROBLOX_OFFICIAL_MCP"),
            "expected_game": os.environ.get("DCC_MCP_ROBLOX_EXPECT_GAME"),
        },
        "official_profile": official_environment_diagnostics(),
        "process_snapshot": process_snapshot(),
        "studio_logs": recent_studio_logs(),
    }
    report = directory / "live-smoke-diagnostics.json"
    report.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return report


def run_checks(call: Any) -> Dict[str, Any]:
    """Run the shared smoke assertions against any MCP call implementation."""

    def check(stage: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return call(method, params)
        except Exception as exc:
            raise RuntimeError(f"smoke stage {stage!r} failed: {exc}") from exc

    def require(condition: bool, stage: str, detail: str) -> None:
        if not condition:
            raise RuntimeError(f"smoke stage {stage!r} failed: {detail}")

    def select_studio(studios: list[Dict[str, Any]]) -> str:
        configured_id = os.environ.get("DCC_MCP_ROBLOX_STUDIO_ID", "").strip()
        if configured_id:
            if any(item.get("studio_id") == configured_id for item in studios):
                return configured_id
            raise RuntimeError(
                "smoke stage 'studio selection' failed: "
                f"configured studio {configured_id!r} is not connected; available={studios}"
            )

        expected_game = os.environ.get("DCC_MCP_ROBLOX_EXPECT_GAME", "").strip()
        if not expected_game:
            return str(studios[0].get("studio_id", ""))

        matches = []
        probes = []
        for studio in studios:
            candidate_id = studio.get("studio_id")
            if not candidate_id:
                continue
            try:
                scene = check(
                    "studio selection",
                    "tools/call",
                    {
                        "name": "roblox_search_game_tree",
                        "arguments": {"studio_id": candidate_id, "query": expected_game},
                    },
                )
                probes.append({"studio_id": candidate_id, "results": scene.get("results", [])})
                if any(item.get("name") == expected_game for item in scene.get("results", [])):
                    matches.append(candidate_id)
            except RuntimeError as exc:
                probes.append({"studio_id": candidate_id, "error": str(exc)})

        if not matches:
            raise RuntimeError(
                "smoke stage 'studio selection' failed: "
                f"no connected Studio contains {expected_game!r}; probes={probes}"
            )
        return str(matches[0])

    def wait_for_play_state(expected: bool, target_studio_id: Optional[str] = None) -> Dict[str, Any]:
        deadline = time.monotonic() + float(os.environ.get("DCC_MCP_ROBLOX_PLAY_WAIT_SECS", "30"))
        state: Dict[str, Any] = {}
        last_error = ""
        selected_studio_id = target_studio_id or studio_id
        while time.monotonic() < deadline:
            try:
                state = check(
                    "play state",
                    "tools/call",
                    {"name": "roblox_get_studio_state", "arguments": {"studio_id": selected_studio_id}},
                )
            except RuntimeError as exc:
                last_error = str(exc)
                time.sleep(0.25)
                continue
            if state.get("is_running") is expected:
                return state
            time.sleep(0.25)
        raise RuntimeError(
            f"smoke stage 'play state' failed: expected is_running={expected}, got {state}, last_error={last_error}"
        )

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
    studio_id = select_studio(studios)

    schema = check(
        "class schema", "tools/call", {"name": "roblox_get_class_schema", "arguments": {"class_name": "Part"}}
    )
    require(schema.get("known") is True, "class schema", f"Part is unknown: {schema}")
    require(
        schema.get("properties", {}).get("Size", {}).get("type") == "Vector3",
        "class schema",
        f"Part.Size schema is missing: {schema}",
    )

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
    require(dry_run.get("dry_run") is True, "transaction dry-run", f"unexpected result: {dry_run}")
    require(dry_run.get("valid") is True, "transaction dry-run", f"unexpected result: {dry_run}")

    auto_stop_after: Optional[float] = None
    configured_auto_stop = os.environ.get("DCC_MCP_ROBLOX_AUTO_STOP_AFTER", "").strip()
    if configured_auto_stop:
        try:
            auto_stop_after = float(configured_auto_stop)
        except ValueError as exc:
            raise RuntimeError(f"invalid DCC_MCP_ROBLOX_AUTO_STOP_AFTER: {configured_auto_stop!r}") from exc

    play_arguments = {"studio_id": studio_id, "action": "start"}
    if auto_stop_after is not None:
        play_arguments["auto_stop_after"] = auto_stop_after

    play_started = check(
        "play start",
        "tools/call",
        {
            "name": "roblox_start_stop_play",
            "arguments": play_arguments,
        },
    )
    require(play_started.get("action") == "start", "play start", f"unexpected result: {play_started}")
    wait_for_play_state(True)
    running_studio_id = next(
        (
            item["studio_id"]
            for item in check(
                "running studio discovery",
                "tools/call",
                {"name": "roblox_list_studios", "arguments": {}},
            )["studios"]
            if item.get("studio_id") and item.get("data_model_type") == "PlayServer"
        ),
        studio_id,
    )
    try:
        play_stopped = check(
            "play stop",
            "tools/call",
            {
                "name": "roblox_start_stop_play",
                "arguments": {"studio_id": running_studio_id, "action": "stop"},
            },
        )
    except RuntimeError as exc:
        if auto_stop_after is None:
            raise
        play_stopped = {"action": "stop", "pending": True, "fallback": "auto_stop", "error": str(exc)}
    require(play_stopped.get("action") == "stop", "play stop", f"unexpected result: {play_stopped}")
    wait_for_play_state(False)
    saved = check(
        "save place",
        "tools/call",
        {
            "name": "roblox_save_place",
            "arguments": {"studio_id": studio_id, "note": "automated smoke"},
        },
    )
    if saved.get("saved") is not True and saved.get("reason") != "unpublished_local_place":
        raise RuntimeError(f"save place returned an unexpected result: {saved}")

    expected_game = os.environ.get("DCC_MCP_ROBLOX_EXPECT_GAME")
    if expected_game:
        scene = check(
            "package scene",
            "tools/call",
            {
                "name": "roblox_search_game_tree",
                "arguments": {"studio_id": studio_id, "query": expected_game},
            },
        )
        if not any(item.get("name") == expected_game for item in scene.get("results", [])):
            raise RuntimeError(f"package scene is missing {expected_game}: {scene}")
        scripts = check(
            "package scripts",
            "tools/call",
            {
                "name": "roblox_script_search",
                "arguments": {
                    "studio_id": studio_id,
                    "query": os.environ.get("DCC_MCP_ROBLOX_EXPECT_SCRIPT_PREFIX", "NeonCheckpoint"),
                },
            },
        )
        script_names = {item.get("name") for item in scripts.get("results", [])}
        expected_scripts = {
            os.environ.get("DCC_MCP_ROBLOX_EXPECT_GAME_SCRIPT", "NeonCheckpointGame"),
            os.environ.get("DCC_MCP_ROBLOX_EXPECT_HUD_SCRIPT", "NeonCheckpointHUD"),
        }
        if not expected_scripts.issubset(script_names):
            raise RuntimeError(f"package scripts are incomplete: {scripts}")

    skills = check("skill search", "tools/call", {"name": "search", "arguments": {"query": "scene"}})
    require(
        any(skill.get("name") == "roblox-scene-authoring" for skill in skills.get("skills", [])),
        "skill search",
        f"scene authoring skill is missing: {skills}",
    )
    loaded = check(
        "skill load", "tools/call", {"name": "load_skill", "arguments": {"skill_name": "roblox-scene-authoring"}}
    )
    require(loaded.get("loaded") is True, "skill load", f"unexpected result: {loaded}")
    creator_store = check(
        "creator store skill",
        "tools/call",
        {"name": "load_skill", "arguments": {"skill_name": "roblox-creator-store"}},
    )
    require(creator_store.get("loaded") is True, "creator store skill", f"unexpected result: {creator_store}")

    official_status: Optional[Dict[str, Any]] = None
    if os.environ.get("DCC_MCP_ROBLOX_ENABLE_OFFICIAL") == "1":
        official_status = check(
            "official MCP status",
            "tools/call",
            {
                "name": "roblox_get_official_mcp_status",
                "arguments": {"probe": True},
            },
        )
        official_tools = check("official tools", "tools/list", {}).get("tools", [])
        official_names = {tool.get("name") for tool in official_tools}
        require(
            "roblox_official__search_asset" in official_names,
            "official tools",
            "search_asset is missing. Enable Assistant > … > Manage MCP Servers > "
            f"Enable Studio as MCP server, then retry; status={official_status}; "
            f"available_names={sorted(official_names)}",
        )
        official_result = check(
            "creator store search",
            "tools/call",
            {
                "name": "call",
                "arguments": {
                    "tool_slug": "roblox_official__search_asset",
                    "arguments": {
                        "query": os.environ.get("DCC_MCP_ROBLOX_CREATOR_STORE_QUERY", "street light"),
                        "scope": "creator_store",
                    },
                },
            },
        )
        require(isinstance(official_result, dict), "creator store search", f"unexpected result: {official_result}")

    event = check(
        "event wait",
        "tools/call",
        {
            "name": "roblox_wait_for_event",
            "arguments": {"event_type": "__dcc_mcp_smoke_never__", "timeout_ms": 50, "poll_ms": 10},
        },
    )
    require(event.get("matched") is False, "event wait", f"unexpected result: {event}")
    audit = check("audit log", "tools/call", {"name": "roblox_get_audit_log", "arguments": {"limit": 1000}})
    require(
        any(entry.get("tool") == "roblox_scene_transaction" for entry in audit.get("entries", [])),
        "audit log",
        f"scene transaction entry is missing: {audit}",
    )
    checks = ["schema", "dry_run", "play", "save"]
    if expected_game:
        checks.append("package")
    checks.extend(["skills", "creator_store_skill", "event_wait", "audit"])
    if os.environ.get("DCC_MCP_ROBLOX_ENABLE_OFFICIAL") == "1":
        checks.extend(["official_tools", "creator_store_search"])
    return {
        "studio_id": studio_id,
        "checks": checks,
        "save_result": "saved" if saved.get("saved") is True else saved["reason"],
        "official_mcp": official_status,
    }


def run(auto_launch: bool = False, install: bool = False, require_official: bool = False) -> None:
    configure_automatic_showcase_defaults(auto_launch)
    port = int(os.environ.get("DCC_MCP_ROBLOX_SMOKE_PORT", "9001"))
    official_enabled = require_official or os.environ.get("DCC_MCP_ROBLOX_ENABLE_OFFICIAL") == "1"
    client = McpProcess(port, enable_official=official_enabled)
    studio = None
    try:
        if auto_launch:
            studio = launch_studio(install)
        print(json.dumps(run_checks(client.call)))
    except Exception as exc:
        report = write_diagnostics(
            str(exc),
            client=client,
            studio=studio,
            auto_launch=auto_launch,
            install=install,
            official_enabled=official_enabled,
        )
        raise RuntimeError(f"{client.diagnostics(str(exc))}; diagnostics={report}") from exc
    finally:
        client.close()
        if studio is not None and os.environ.get("DCC_MCP_ROBLOX_SMOKE_CLOSE_STUDIO") == "1":
            if studio.poll() is None:
                studio.terminate()
                try:
                    studio.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    studio.kill()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--launch-studio", action="store_true", help="Launch Roblox Studio when no plugin is connected."
    )
    parser.add_argument(
        "--install-plugin", action="store_true", help="Install the bundled plugin before launching Studio."
    )
    parser.add_argument(
        "--enable-official-mcp",
        action="store_true",
        help="Start the adapter with Roblox Studio's official MCP compatibility route enabled.",
    )
    parser.add_argument(
        "--diagnostic-dir",
        help="Directory for live-smoke-diagnostics.json on failure.",
    )
    options = parser.parse_args()
    if options.diagnostic_dir:
        os.environ["DCC_MCP_ROBLOX_DIAGNOSTIC_DIR"] = options.diagnostic_dir
    run(
        auto_launch=options.launch_studio or os.environ.get("DCC_MCP_ROBLOX_AUTO_LAUNCH") == "1",
        install=options.install_plugin,
        require_official=options.enable_official_mcp,
    )
