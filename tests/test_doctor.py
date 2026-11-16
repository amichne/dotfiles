from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .conftest import Home
from .test_df import command, initialize


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def prepare(home: Home) -> None:
    initialize(home)
    recipes = home.path / ".config/austincomplete/recipes"
    cache = home.path / ".cache/austincomplete/zsh"
    cache.mkdir(parents=True)
    for recipe in recipes.glob("*.json"):
        _ = (cache / f"_{recipe.stem}").write_text(f"#compdef {recipe.stem}\n")
    config = home.path / ".config/mise/config.toml"
    _ = config.write_text(
        '[tools]\nnode = "1.2.3"\n[vars]\nsetup_brew_formulae = ""\nsetup_brew_casks = ""\n'
    )
    mise = home.tools / "mise"
    _ = mise.write_text(
        f'#!{sys.executable}\nimport sys\nassert sys.argv[1] == "where"\nprint("/fixture/node/1.2.3")\n'
    )
    mise.chmod(0o755)
    nvim = home.tools / "nvim"
    payload = json.dumps(
        {
            "version": 1,
            "servers": [{"server": "fixture", "executable": "nvim", "outcome": "ENABLED"}],
        }
    )
    _ = nvim.write_text(f"#!{sys.executable}\nprint({payload!r})\n")
    nvim.chmod(0o755)
    for name in ("ty", "ruff", "biome", "starship", "atuin", "zoxide", "fzf"):
        executable = home.tools / name
        _ = executable.write_text("#!/bin/sh\nexit 99\n")
        executable.chmod(0o755)
    _ = (home.path / ".zshrc").write_text("touch SHOULD_NOT_EXIST\n")


def test_doctor_healthy_is_read_only(home: Home) -> None:
    prepare(home)
    before = snapshot(home.path)
    result = subprocess.run(
        ["df", "doctor", "--json"],
        cwd=home.path.parent,
        env={**home.env, "PATH": f"{home.path / '.local/bin'}:{home.env['PATH']}"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "healthy"
    assert {row["name"] for row in report["items"]} >= {"repository", "mise:node@1.2.3", "pi:ty"}
    assert snapshot(home.path) == before


def test_doctor_missing_dependency_and_invalid_shell(home: Home) -> None:
    prepare(home)
    (home.tools / "ty").unlink()
    _ = (home.path / ".zshrc").write_text("if then\n")
    before = snapshot(home.path)
    result = command(home, "doctor", "--json")
    assert result.returncode == 1
    rows = {row["name"]: row for row in json.loads(result.stdout)["items"]}
    assert rows["pi:ty"]["outcome"] == "unavailable"
    assert rows["shell:.zshrc"]["outcome"] == "failed"
    assert rows["pi:ty"]["repair"]
    assert snapshot(home.path) == before


def test_doctor_rejected_repository_stops_probes(home: Home) -> None:
    result = command(home, "doctor", "--json")
    assert result.returncode == 1
    rows = json.loads(result.stdout)["items"]
    assert len(rows) == 1
    assert rows[0]["detail"] == "missing-repository"


def test_doctor_detects_missing_cache_and_selected_version(home: Home) -> None:
    prepare(home)
    (home.path / ".cache/austincomplete/zsh/_mise").unlink()
    _ = (home.tools / "mise").write_text(
        f'#!{sys.executable}\nimport sys\nprint("/pin" if "@" in sys.argv[-1] else "/other")\n'
    )
    result = command(home, "doctor", "--json")
    assert result.returncode == 1
    rows = {row["name"]: row for row in json.loads(result.stdout)["items"]}
    assert rows["completion:mise"]["outcome"] == "failed"
    assert rows["mise:node@1.2.3"]["outcome"] == "failed"


def test_doctor_native_editor_probe_preserves_home(home: Home) -> None:
    prepare(home)
    native = shutil.which("nvim")
    assert native is not None
    (home.tools / "nvim").unlink()
    (home.tools / "nvim").symlink_to(native)
    before = snapshot(home.path)
    result = command(home, "doctor", "--json")
    rows = {row["name"]: row for row in json.loads(result.stdout)["items"]}
    assert rows["editor:ty"]["outcome"] == "passed", result.stdout
    assert rows["editor:kotlin_lsp"]["outcome"] == "unavailable"
    assert snapshot(home.path) == before
