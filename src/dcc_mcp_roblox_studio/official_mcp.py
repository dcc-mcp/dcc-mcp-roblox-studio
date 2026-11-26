"""Compatibility proxy for Roblox Studio's built-in stdio MCP server."""

from __future__ import annotations

import json
import os
import queue
import re
import shlex
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional


class OfficialMcpError(RuntimeError):
    """Raised when the official Roblox MCP process cannot serve a request."""


def default_official_command() -> Optional[str]:
    """Return Roblox's installed StudioMCP launcher when it is available."""
    configured = os.environ.get("DCC_MCP_ROBLOX_OFFICIAL_MCP")
    if configured:
        return configured
    if os.name == "nt":
        path = Path(os.environ.get("LOCALAPPDATA", "")) / "Roblox" / "mcp.bat"
        if path.exists():
            return str(path)
    return None


def _command_args(command: str) -> List[str]:
    """Convert a configured command into a subprocess argument vector."""
    normalized = command.strip()
    if os.name == "nt" and normalized.strip('"').lower().endswith((".bat", ".cmd")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", normalized]
    parts = shlex.split(command, posix=os.name != "nt")
    if os.name == "nt":
        parts = [part[1:-1] if len(part) > 1 and part[0] == part[-1] == '"' else part for part in parts]
    return parts


def _redact(text: str) -> str:
    """Remove credential-shaped values before diagnostic text is exposed."""
    return re.sub(
        r"(?i)(token|secret|password|authorization|bearer)\s*[:=]\s*[^\s,;]+",
        r"\1=<redacted>",
        text,
    )


def _launcher_path(command: Optional[str]) -> Optional[Path]:
    """Return the configured launcher path when the command names a file."""
    if not command:
        return None
    normalized = command.strip().strip('"')
    if os.name == "nt" and normalized.lower().endswith((".bat", ".cmd")):
        candidate = Path(normalized).expanduser()
        return candidate if candidate.is_file() else None
    try:
        first = _command_args(command)[0]
    except (IndexError, ValueError):
        return None
    candidate = Path(first).expanduser()
    return candidate if candidate.is_file() else None


def _launcher_binary(command: Optional[str]) -> Optional[Path]:
    """Resolve the executable behind Roblox's Windows batch launcher."""
    launcher = _launcher_path(command)
    if launcher is None:
        return None
    if launcher.suffix.lower() not in {".bat", ".cmd"}:
        return launcher
    try:
        text = launcher.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    candidates = re.findall(r'"([^"\r\n]*StudioMCP\.exe)"', text, flags=re.IGNORECASE)
    for value in candidates:
        candidate = Path(value).expanduser()
        if candidate.is_file():
            return candidate
    return None


def _file_summary(path: Path) -> Dict[str, Any]:
    """Return metadata for a local support file without exposing its contents."""
    try:
        stat = path.stat()
    except OSError as exc:
        return {"path": str(path), "exists": False, "error": str(exc)}
    return {"path": str(path), "exists": True, "size": stat.st_size}


def official_environment_diagnostics(command: Optional[str] = None) -> Dict[str, Any]:
    """Collect safe, local diagnostics for the installed official MCP launcher."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    roblox_root = Path(local_app_data) / "Roblox" if local_app_data else Path()
    client_settings = roblox_root / "ClientSettings" / "ClientAppSettings.json"
    studio_settings = roblox_root / "ClientSettings" / "StudioAppSettings.json"
    auth_token = roblox_root / "StudioMCP" / "auth.token"
    result: Dict[str, Any] = {
        "client_settings": _file_summary(client_settings),
        "studio_settings": _file_summary(studio_settings),
        "auth_token": _file_summary(auth_token),
    }
    if auth_token.is_file():
        try:
            result["auth_token"]["length"] = len(auth_token.read_bytes())
        except OSError as exc:
            result["auth_token"]["read_error"] = str(exc)

    if client_settings.is_file():
        try:
            settings = json.loads(client_settings.read_text(encoding="utf-8"))
            result["client_settings"]["mcp_flags"] = {
                str(key): value for key, value in settings.items() if str(key).startswith("FFlagStudioMCP")
            }
        except (OSError, json.JSONDecodeError) as exc:
            result["client_settings"]["parse_error"] = str(exc)

    binary = _launcher_binary(command or default_official_command())
    result["launcher_binary"] = str(binary) if binary else None
    if binary is None or binary.stem.lower() != "studiomcp":
        return result
    try:
        completed = subprocess.run(
            [str(binary), "--print-flags"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        result["launcher_flags"] = {
            "returncode": completed.returncode,
            "stdout": _redact(completed.stdout[-6000:]),
            "stderr": _redact(completed.stderr[-2000:]),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        result["launcher_flags"] = {"error": str(exc)}
    return result


class OfficialMcpProxy:
    """Serialize MCP requests to the official StudioMCP stdio process.

    Roblox ships new official tools independently from this adapter. The proxy
    keeps those tools discoverable without copying private implementation logic
    into the DCC-MCP plugin.
    """

    def __init__(
        self,
        command: Optional[str] = None,
        *,
        tool_prefix: str = "roblox_official__",
        timeout: float = 15.0,
    ) -> None:
        self.command = command or default_official_command()
        self.tool_prefix = tool_prefix
        self.timeout = timeout
        self._process: Optional[subprocess.Popen[str]] = None
        self._stdout_queue: Optional[queue.Queue[Optional[str]]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_lines: "deque[str]" = deque(maxlen=100)
        self._stderr_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._next_id = 0
        self._tools: Optional[List[Dict[str, Any]]] = None
        self._last_error: Optional[str] = None

    @property
    def enabled(self) -> bool:
        """Return whether a launcher command was configured or detected."""
        return bool(self.command)

    def start(self) -> None:
        """Start the official MCP process and complete its handshake."""
        with self._lock:
            if self._process is not None:
                return
            if not self.command:
                raise OfficialMcpError(
                    "Roblox Studio's official MCP launcher was not found. "
                    "Set DCC_MCP_ROBLOX_OFFICIAL_MCP or pass --official-mcp-command."
                )
            try:
                self._process = subprocess.Popen(
                    _command_args(self.command),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                self._stderr_lines.clear()
                self._stdout_queue = queue.Queue()
                self._reader_thread = threading.Thread(
                    target=self._pump_stdout,
                    args=(self._process, self._stdout_queue),
                    daemon=True,
                    name="roblox-official-mcp-reader",
                )
                self._reader_thread.start()
                self._stderr_thread = threading.Thread(
                    target=self._pump_stderr,
                    args=(self._process,),
                    daemon=True,
                    name="roblox-official-mcp-stderr-reader",
                )
                self._stderr_thread.start()
                self._request_locked(
                    "initialize",
                    {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "dcc-mcp-roblox-studio", "version": "0.1.1"},
                    },
                )
                self._notify_locked("notifications/initialized", {})
                self._last_error = None
            except Exception as exc:
                self._last_error = str(exc)
                self.close()
                raise

    def close(self) -> None:
        """Terminate the official process and clear its discovery cache."""
        with self._lock:
            process = self._process
            self._process = None
            self._stdout_queue = None
            self._tools = None
            if process is None:
                return
            try:
                if process.stdin is not None:
                    process.stdin.close()
            except OSError:
                pass
            try:
                process.terminate()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
            reader = self._reader_thread
            self._reader_thread = None
            if reader is not None:
                reader.join(timeout=1)
            stderr_reader = self._stderr_thread
            self._stderr_thread = None
            if stderr_reader is not None:
                stderr_reader.join(timeout=1)

    def status(self, *, probe: bool = False) -> Dict[str, Any]:
        """Return safe launcher and process diagnostics for smoke runners."""
        with self._lock:
            launcher = _launcher_path(self.command)
            result: Dict[str, Any] = {
                "enabled": self.enabled,
                "command_configured": bool(self.command),
                "launcher": str(launcher) if launcher else self.command,
                "launcher_exists": launcher is not None,
                "process_id": self._process.pid if self._process is not None else None,
                "returncode": self._process.poll() if self._process is not None else None,
                "stderr": self._stderr_text(),
                "last_error": self._last_error,
                "environment": official_environment_diagnostics(self.command),
            }
            if not probe:
                return result
            try:
                tools = self.list_tools()
                result.update(
                    {
                        "ready": bool(tools),
                        "tool_count": len(tools),
                        "tool_names": [str(tool.get("name", "")) for tool in tools],
                    }
                )
            except Exception as exc:
                self._last_error = str(exc)
                result.update({"ready": False, "tool_count": 0, "tool_names": [], "error": str(exc)})
            result["process_id"] = self._process.pid if self._process is not None else None
            result["returncode"] = self._process.poll() if self._process is not None else None
            result["stderr"] = self._stderr_text()
            result["last_error"] = self._last_error
            return result

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return official tool schemas with an adapter-owned namespace."""
        with self._lock:
            self.start()
            if self._tools is None:
                result = self._request_locked("tools/list", {})
                self._tools = list(result.get("tools", []))
            tools = []
            for original in self._tools:
                tool = dict(original)
                original_name = str(tool.get("name", ""))
                tool["name"] = self.tool_prefix + original_name
                description = str(tool.get("description", "")).strip()
                tool["description"] = (
                    "Official Roblox Studio MCP compatibility route. " + description
                    if description
                    else "Official Roblox Studio MCP compatibility route."
                )
                tools.append(tool)
            return tools

    def call(self, exposed_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call one official tool using its adapter-prefixed name."""
        if not exposed_name.startswith(self.tool_prefix):
            raise OfficialMcpError("Tool is outside the official Roblox MCP namespace")
        original_name = exposed_name[len(self.tool_prefix) :]
        with self._lock:
            self.start()
            result = self._request_locked("tools/call", {"name": original_name, "arguments": arguments})
            if not isinstance(result, dict):
                return {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}]}
            return result

    def _notify_locked(self, method: str, params: Dict[str, Any]) -> None:
        process = self._require_process_locked()
        if process.stdin is None:
            raise OfficialMcpError("Official Roblox MCP stdin is unavailable")
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def _request_locked(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        process = self._require_process_locked()
        if process.stdin is None or self._stdout_queue is None:
            raise OfficialMcpError("Official Roblox MCP stdio is unavailable")
        self._next_id += 1
        request_id = self._next_id
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()

        while True:
            try:
                line = self._stdout_queue.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise OfficialMcpError(
                    f"Official Roblox MCP did not reply within {self.timeout}s; stderr={self._stderr_text()}"
                ) from exc
            if line is None:
                code = process.poll()
                raise OfficialMcpError(
                    f"Official Roblox MCP exited before replying (code={code}); stderr={self._stderr_text()}"
                )
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") != request_id:
                continue
            if response.get("error") is not None:
                error = response["error"]
                raise OfficialMcpError(
                    f"{error.get('message', 'Official Roblox MCP request failed')}; stderr={self._stderr_text()}"
                )
            result = response.get("result")
            return result if isinstance(result, dict) else {"value": result}

    def _require_process_locked(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise OfficialMcpError("Official Roblox MCP process is not running")
        return self._process

    @staticmethod
    def _pump_stdout(
        process: subprocess.Popen[str],
        output: "queue.Queue[Optional[str]]",
    ) -> None:
        """Read process output without blocking the MCP request lock."""
        if process.stdout is None:
            output.put(None)
            return
        for line in process.stdout:
            output.put(line)
        output.put(None)

    def _stderr_text(self) -> str:
        """Return a bounded stderr tail without exposing credential-shaped data."""
        return _redact("".join(self._stderr_lines)[-2000:])

    def _pump_stderr(self, process: subprocess.Popen[str]) -> None:
        """Read official-process diagnostics without blocking MCP requests."""
        if process.stderr is None:
            return
        for line in process.stderr:
            self._stderr_lines.append(line)
