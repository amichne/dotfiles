from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from .conftest import Home
from .test_agent_checks import configure
from .test_agent_install import install


def planned(home: Home, owner: Path) -> dict[str, object]:
    result = install(home, owner)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def apply(home: Home, owner: Path, plan: dict[str, object]) -> dict[str, object]:
    result = install(home, owner, "--apply", "--expected-plan", str(plan["planId"]))
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("change_source_again", [False, True])
def test_partial_baseline_update_keeps_each_resource_owner(
    home: Home, change_source_again: bool
) -> None:
    owner = configure(home)
    _ = apply(home, owner, planned(home, owner))
    receipt_path = home.path / ".local/state/agent-engineering/installation.json"
    if not change_source_again:
        # Live installations made by the prior release have no per-resource map.
        legacy = json.loads(receipt_path.read_bytes())
        _ = legacy.pop("baselines")
        _ = receipt_path.write_text(json.dumps(legacy))
    pi = home.path / ".pi/agent"
    target = pi / "AGENTS.md"
    old_pi = target.read_bytes()
    extension = pi / "extensions/engineering-checks.ts"
    old_extension = extension.read_bytes()
    baseline = home.path / ".config/agent-engineering/B0.md"
    original = baseline.read_bytes()
    _ = baseline.write_bytes(original.replace(b"Measure results.", b"Measure current results."))
    template = baseline.with_name("pi-extension.ts")
    _ = template.write_bytes(template.read_bytes() + b"\n// Updated adapter fixture.\n")
    update = planned(home, owner)
    original_mode = stat.S_IMODE(pi.stat().st_mode)
    pi.chmod(0o500)
    try:
        failed = install(home, owner, "--apply", "--expected-plan", str(update["planId"]))
        assert failed.returncode == 1 and "Permission denied" in failed.stdout, failed.stdout
    finally:
        pi.chmod(original_mode)
    assert target.read_bytes() == old_pi
    assert extension.read_bytes() == old_extension
    assert (home.path / ".codex/AGENTS.md").read_bytes() != old_pi
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["status"] == "partial-install"
    if change_source_again:
        _ = baseline.write_bytes(original.replace(b"Measure results.", b"Measure each result."))
    retry = planned(home, owner)
    # A recovery receipt must not authorize a user edit in the untouched old block.
    _ = target.write_bytes(old_pi.replace(b"Measure results.", b"Keep this user edit."))
    assert install(home, owner).returncode == 1
    _ = target.write_bytes(old_pi)
    _ = extension.write_bytes(old_extension + b"\n// User edit.\n")
    assert "unowned-pi-extension" in install(home, owner).stdout
    _ = extension.write_bytes(old_extension)
    _ = apply(home, owner, retry)
    assert baseline.read_bytes() in target.read_bytes()
    assert target.read_bytes() == (home.path / ".codex/AGENTS.md").read_bytes()
    assert extension.read_bytes() == template.read_bytes()


def test_noop_keeps_the_last_real_backup_reference(home: Home) -> None:
    owner = configure(home)
    first = apply(home, owner, planned(home, owner))
    backup = Path(str(first["backup"]))
    manifest = (backup / "manifest.json").read_bytes()
    noop = planned(home, owner)
    assert noop["changes"] == []
    repeated = apply(home, owner, noop)
    assert repeated["changed"] == []
    assert repeated["backup"] == str(backup)
    assert (backup / "manifest.json").read_bytes() == manifest
    receipt = json.loads(
        (home.path / ".local/state/agent-engineering/installation.json").read_bytes()
    )
    assert receipt["backup"] == str(backup)


@pytest.mark.parametrize("filename", ["kotlin", "kotlin.lock"])
def test_kotlin_change_invalidates_install_plan_before_writes(home: Home, filename: str) -> None:
    owner = configure(home)
    old = planned(home, owner)
    tool = owner / filename
    _ = tool.write_bytes(tool.read_bytes() + b"\n# changed after plan\n")
    fresh = planned(home, owner)
    assert fresh["planId"] != old["planId"]
    stale = install(home, owner, "--apply", "--expected-plan", str(old["planId"]))
    assert stale.returncode == 1 and "stale-install-plan" in stale.stdout
    assert not (home.path / ".codex/AGENTS.md").exists()
    assert not (home.path / ".pi/agent/AGENTS.md").exists()
