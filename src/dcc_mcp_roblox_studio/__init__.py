"""Roblox Studio adapter for the DCC-MCP ecosystem."""

from dcc_mcp_roblox_studio.__version__ import __version__
from dcc_mcp_roblox_studio.server import RobloxStudioMcpServer, main

__all__ = ["RobloxStudioMcpServer", "__version__", "main"]
