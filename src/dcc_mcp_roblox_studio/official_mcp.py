"""Compatibility proxy for Roblox Studio's built-in stdio MCP server."""

from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import threading
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
        self._lock = threading.RLock()
        self._next_id = 0
        self._tools: Optional[List[Dict[str, Any]]] = None

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
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                self._stdout_queue = queue.Queue()
                self._reader_thread = threading.Thread(
                    target=self._pump_stdout,
                    args=(self._process, self._stdout_queue),
                    daemon=True,
                    name="roblox-official-mcp-reader",
                )
                self._reader_thread.start()
                self._request_locked(
                    "initialize",
                    {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "dcc-mcp-roblox-studio", "version": "0.1.1"},
                    },
                )
                self._notify_locked("notifications/initialized", {})
            except Exception:
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

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return official tool schemas with an adapter-owned namespace."""
        with self._lock:
            self.start()
            if self._tools is None or not self._tools:
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
                raise OfficialMcpError(f"Official Roblox MCP did not reply within {self.timeout}s") from exc
            if line is None:
                code = process.poll()
                raise OfficialMcpError(f"Official Roblox MCP exited before replying (code={code})")
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") != request_id:
                continue
            if response.get("error") is not None:
                error = response["error"]
                raise OfficialMcpError(str(error.get("message", "Official Roblox MCP request failed")))
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
