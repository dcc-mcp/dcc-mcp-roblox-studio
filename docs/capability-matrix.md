# Roblox Studio capability matrix

This adapter is an integration layer for the DCC-MCP ecosystem. It is not an
official Roblox product and does not replace Roblox Studio's built-in MCP
server. The official server remains authoritative for Roblox-owned features.

The integration is intentionally complementary. The official server provides
Roblox-owned behavior and the latest Studio capabilities, while DCC-MCP adds a
shared control plane for discovery, multi-instance routing, lifecycle
management, auditability, and cross-DCC orchestration.

## Coverage model

| Capability family | Native DCC-MCP route | Official compatibility route | Notes |
| --- | --- | --- | --- |
| Studio discovery and multi-instance routing | `roblox_list_studios`, `studio_id` on every native tool | Official `studio_id` arguments are forwarded unchanged | Shared `dcc-mcp-core` bridge metadata and lifecycle |
| DataModel search and inspection | `roblox_search_game_tree`, `roblox_inspect_instance` | `roblox_official__search_game_tree`, `roblox_official__inspect_instance` | Native route is optimized for common agent workflows |
| Script read and source search | `roblox_script_read`, `roblox_script_search`, `roblox_script_grep` | `roblox_official__script_read`, `roblox_official__script_search`, `roblox_official__script_grep` | Native writes use Studio undo recordings |
| Script editing | `roblox_multi_edit` | `roblox_official__multi_edit` | Both routes preserve the official schema where available |
| Instance and service editing | Create, modify, clone, move, delete, selection, service insertion, class schemas, scene transactions | Official tools are forwarded when installed | Native operations use typed values and ChangeHistoryService |
| Playtest and console | Native play control and console capture | Official play, console, screenshot, video, and input tools | Official route is preferred for Studio-owned automation |
| Asset and AI generation | — | Official asset search, insert, upload, material, mesh, avatar, animation, and generation tools | Capability depends on the installed StudioMCP version and account permissions |
| Luau and Studio skills | — | Official `execute_luau`, `skill`, and `subagent` tools | Kept behind the official namespace to preserve Roblox behavior |
| Place persistence and feedback | Native `roblox_save_place` | Official save and feedback tools | Studio permissions still apply |
| Gateway operations | DCC-MCP gateway discovery, REST, MCP, audit, and lifecycle | Available around the adapter process | Shared with other DCC adapters |
| Event and operation observability | Filtered `roblox_bridge_events`, `roblox_wait_for_event`, `roblox_get_audit_log`, stable operation IDs, and dry-run validation | Official diagnostics remain available when installed | Audit parameters redact script source and content |
| Official MCP readiness and diagnostics | `roblox_get_official_mcp_status`, live smoke diagnostic artifact | Installed `StudioMCP` launcher and live `tools/list` | Reports launcher, process, stderr, tool count, Studio logs, and process state without exposing credentials |
| DCC-MCP Skills | `search`, `describe`, `load_skill`, `call` with `roblox-scene-authoring` and `roblox-creator-store` | Official `skill` and `subagent` tools are forwarded when installed | Creator Store search and insertion keep the live official schemas |
| Fallback UI control | DCC-MCP `ui-control` skill | Roblox native UI input tools | Use only when a structured tool cannot express the operation |

## Official tool compatibility

The sidecar starts the locally installed `%LOCALAPPDATA%\\Roblox\\mcp.bat`
launcher when official compatibility is enabled. It performs the MCP
initialize handshake, queries the live `tools/list`, prefixes each name with
`roblox_official__`, and forwards `tools/call` requests. This means new
official tools can become available through the adapter without a parallel
adapter release, provided the local Studio installation exposes them.

The compatibility route includes the official categories documented by Roblox,
including script editing, DataModel inspection, Luau execution, asset search
and insertion, generation jobs, playtesting, console output, screenshots,
video capture, player input, HTTP access, Studio skills, place saving, and
feedback. It does not claim that every account or Studio build exposes every
category.

## Community capability alignment

The native tool surface includes the recurring capabilities found in community
Roblox Studio MCP projects, including tree search, instance inspection,
property and attribute edits, selection, service insertion, cloning, moving,
deletion, script search, source grep, play control, console access, and undo or
redo. The official compatibility namespace covers the larger Roblox-owned
surface without copying private implementation details into this repository.

The resulting architecture gives agents one discovery and routing contract
across Roblox Studio and the wider DCC-MCP fleet while retaining the official
Roblox MCP behavior when that behavior is required.
