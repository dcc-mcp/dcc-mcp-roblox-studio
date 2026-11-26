"""Offline contracts for the live smoke runner and playable showcase."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_live_smoke_runner_has_safe_read_only_probe() -> None:
    source = (ROOT / "scripts" / "live_smoke.py").read_text(encoding="utf-8")
    assert "DccMcpAutomatedProbe" in source
    assert '"dry_run": True' in source
    assert '"roblox_wait_for_event"' in source
    assert '"roblox_get_audit_log"' in source


def test_playable_showcase_contract_and_asset_attribution_exist() -> None:
    example = (ROOT / "docs" / "examples" / "neon-checkpoint-run.md").read_text(encoding="utf-8")
    asset = ROOT / "docs" / "assets" / "game-icons" / "flag-objective.svg"
    assert "NeonCheckpointRun" in example
    assert "NeonCheckpointGame" in example
    assert "NeonCheckpointHUD" in example
    assert "CC BY 3.0" in example
    assert asset.exists()
