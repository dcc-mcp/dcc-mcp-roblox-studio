"""Offline contracts for the live smoke runner and playable showcase."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_live_smoke_runner_has_protocol_probe_and_diagnostics() -> None:
    source = (ROOT / "scripts" / "live_smoke.py").read_text(encoding="utf-8")
    assert "DccMcpAutomatedProbe" in source
    assert '"dry_run": True' in source
    assert '"roblox_wait_for_event"' in source
    assert '"roblox_get_audit_log"' in source
    assert '"roblox_start_stop_play"' in source
    assert '"roblox_save_place"' in source
    assert 'checks = ["schema", "dry_run", "play", "save"]' in source
    assert "--launch-studio" in source
    assert "--install-plugin" in source
    assert "DCC_MCP_ROBLOX_DEFAULT_PACKAGE" in source
    assert "configure_automatic_showcase_defaults" in source
    assert "DCC_MCP_ROBLOX_EXPECT_GAME" in source
    assert "roblox_get_official_mcp_status" in source
    assert "DCC_MCP_ROBLOX_DIAGNOSTIC_DIR" in source
    assert "smoke stage" in source
    assert "adapter_stderr" in source


def test_ci_protocol_smoke_is_registered() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "protocol-smoke" in workflow
    assert "python scripts/ci_smoke.py" in workflow
    ci_smoke = (ROOT / "scripts" / "ci_smoke.py").read_text(encoding="utf-8")
    assert "fake_official_command" in ci_smoke
    assert "DCC_MCP_ROBLOX_ENABLE_OFFICIAL" in ci_smoke

    live_workflow = (ROOT / ".github" / "workflows" / "live-studio-smoke.yml").read_text(encoding="utf-8")
    assert "pull_request" in live_workflow
    assert "branches: [main]" in live_workflow
    assert "workflow_dispatch" in live_workflow
    assert "roblox-studio" in live_workflow
    assert "--launch-studio --install-plugin" in live_workflow
    assert "Reset runner Studio" in live_workflow
    assert "DCC_MCP_ROBLOX_DEFAULT_PACKAGE" in live_workflow
    assert "DCC_MCP_ROBLOX_EXPECT_GAME" in live_workflow
    assert "--enable-official-mcp" in live_workflow
    assert "live-studio-diagnostics" in live_workflow
    assert "upload-artifact" in live_workflow


def test_playable_showcase_contract_and_asset_attribution_exist() -> None:
    example = (ROOT / "docs" / "examples" / "neon-checkpoint-run.md").read_text(encoding="utf-8")
    asset = ROOT / "docs" / "assets" / "game-icons" / "flag-objective.svg"
    assert "NeonCheckpointRun" in example
    assert "NeonCheckpointGame" in example
    assert "NeonCheckpointHUD" in example
    assert "CC BY 3.0" in example
    assert asset.exists()


def test_manhattan_showcase_contract_and_creator_store_skill_exist() -> None:
    example = (ROOT / "docs" / "examples" / "manhattan-dash.md").read_text(encoding="utf-8")
    skill = ROOT / "src" / "dcc_mcp_roblox_studio" / "skills" / "roblox-creator-store" / "SKILL.md"
    assert "ManhattanReplica" in example
    assert "search_asset" in example
    assert "insert_asset" in example
    assert skill.exists()
