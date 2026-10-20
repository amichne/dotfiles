from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .conftest import Home
from .test_agent_checks import configure


def install(home: Home, owner: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(home.path / ".config/agent-engineering/check.py"),
            "install",
            "--kotlin",
            str(owner / "kotlin"),
            "--assessment",
            str(owner / "scripts/assess.py"),
            "--vale",
            str(owner / "vale"),
            *extra,
        ],
        cwd=home.path,
        env=home.env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_install_preserves_private_files_and_is_idempotent(home: Home) -> None:
    owner = configure(home)
    codex = home.path / ".codex"
    codex.mkdir()
    original = b"# My instructions\n\nKeep this exact text.\n"
    _ = (codex / "AGENTS.md").write_bytes(original)
    hooks = {
        "hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": "existing-command", "timeout": 5}]}]
        }
    }
    _ = (codex / "hooks.json").write_text(json.dumps(hooks))
    settings = codex / "config.toml"
    _ = settings.write_text(
        'model = "keep-model"\n[hooks.state.fixture]\ntrusted_hash = "keep-trust"\n'
    )
    before_settings = settings.read_bytes()
    append = home.path / ".pi/agent/APPEND_SYSTEM.md"
    _ = append.write_bytes(b"Keep the existing Pi feature instructions.\n")
    append_before = append.read_bytes()
    planned = install(home, owner)
    assert planned.returncode == 0, planned.stderr
    plan = json.loads(planned.stdout)
    assert (codex / "AGENTS.md").read_bytes() == original
    result = install(home, owner, "--apply", "--expected-plan", plan["planId"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert (codex / "AGENTS.md").read_bytes().startswith(original)
    assert (codex / "AGENTS.md").read_bytes().count(b"# Engineering baseline B0") == 1
    assert (
        json.loads((codex / "hooks.json").read_bytes())["hooks"]["Stop"][0]
        == hooks["hooks"]["Stop"][0]
    )
    assert settings.read_bytes() == before_settings and append.read_bytes() == append_before
    after = (codex / "AGENTS.md").read_bytes()
    again = json.loads(install(home, owner).stdout)
    assert again["changes"] == []
    assert install(home, owner, "--apply", "--expected-plan", again["planId"]).returncode == 0
    assert (codex / "AGENTS.md").read_bytes() == after
    edited = after.replace(b"Parse, do not validate.", b"Keep this user edit inside the block.")
    assert edited != after
    _ = (codex / "AGENTS.md").write_bytes(edited)
    rejected = install(home, owner)
    assert rejected.returncode == 1 and "modified-managed-baseline" in rejected.stdout
    assert (codex / "AGENTS.md").read_bytes() == edited


def test_stale_plan_and_malformed_block_never_overwrite(home: Home) -> None:
    owner = configure(home)
    codex = home.path / ".codex"
    codex.mkdir()
    target = codex / "AGENTS.md"
    _ = target.write_text("Private.\n")
    plan = install(home, owner)
    assert plan.returncode == 0, plan.stderr
    _ = target.write_text("Changed after the plan.\n")
    stale = install(home, owner, "--apply", "--expected-plan", json.loads(plan.stdout)["planId"])
    assert stale.returncode == 1 and "stale-install-plan" in stale.stdout
    assert target.read_text() == "Changed after the plan.\n"
    assert not (codex / "hooks.json").exists()
    _ = target.write_text("<!-- agent-engineering:B0 begin -->\nUnclosed.\n")
    assert install(home, owner).returncode == 1
    assert not (codex / "hooks.json").exists()


def test_unowned_extension_and_symlink_are_rejected_before_writes(home: Home) -> None:
    owner = configure(home)
    extension = home.path / ".pi/agent/extensions/engineering-checks.ts"
    extension.parent.mkdir(exist_ok=True)
    _ = extension.write_text("User implementation.\n")
    result = install(home, owner)
    assert result.returncode == 1 and "unowned-pi-extension" in result.stdout
    assert not (home.path / ".codex/AGENTS.md").exists()
    extension.unlink()
    target = home.path / ".codex"
    target.mkdir()
    private = home.tools / "private.md"
    _ = private.write_text("Private.\n")
    (target / "AGENTS.md").symlink_to(private)
    assert install(home, owner).returncode == 1
    assert private.read_text() == "Private.\n"
