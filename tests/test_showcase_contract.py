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
    assert '"checks": ["schema", "dry_run", "play", "save"' in source
    assert "--launch-studio" in source
    assert "--install-plugin" in source
    assert "smoke stage" in source
    assert "adapter_stderr" in source


def test_ci_protocol_smoke_is_registered() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "protocol-smoke" in workflow
    assert "python scripts/ci_smoke.py" in workflow


def test_playable_showcase_contract_and_asset_attribution_exist() -> None:
    example = (ROOT / "docs" / "examples" / "neon-checkpoint-run.md").read_text(encoding="utf-8")
    asset = ROOT / "docs" / "assets" / "game-icons" / "flag-objective.svg"
    assert "NeonCheckpointRun" in example
    assert "NeonCheckpointGame" in example
    assert "NeonCheckpointHUD" in example
    assert "CC BY 3.0" in example
    assert asset.exists()
