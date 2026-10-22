from __future__ import annotations

import json
import subprocess
import sys

import pytest

from .conftest import Home


def command(fixture: Home, *args: str) -> subprocess.CompletedProcess[str]:
    return fixture.run(sys.executable, str(fixture.path / "scripts/df.py"), *args)


def git(fixture: Home, *args: str) -> subprocess.CompletedProcess[str]:
    return fixture.run(
        "/usr/bin/git",
        f"--git-dir={fixture.path / '.dotfiles.git'}",
        f"--work-tree={fixture.path}",
        *args,
    )


def initialize(fixture: Home) -> None:
    result = fixture.run("/usr/bin/git", "init", "--bare", str(fixture.path / ".dotfiles.git"))
    assert result.returncode == 0, result.stderr
    for args in (
        ("config", "user.name", "Fixture"),
        ("config", "user.email", "fixture@example.invalid"),
        ("remote", "add", "origin", "git@github.com:amichne/dotfiles.git"),
    ):
        assert git(fixture, *args).returncode == 0


def test_df_uses_one_bare_home_index(home: Home) -> None:
    initialize(home)
    selected = ".config/starship.toml"
    _ = (home.path / selected).write_text("selected\n")
    _ = (home.path / "untouched").write_text("private\n")
    result = command(home, "add", selected)
    assert result.returncode == 0, result.stderr
    assert git(home, "diff", "--cached", "--name-only").stdout.splitlines() == [selected]
    assert (home.path / ".dotfiles.git/index").is_file()
    assert not (home.path / ".git").exists()
    result = command(home, "commit", "-m", "Selected file")
    assert result.returncode == 0, result.stderr
    assert command(home, "git", "show", f"HEAD:{selected}").stdout == "selected\n"
    assert command(home, "diff").stdout == ""
    assert (home.path / "untouched").read_text() == "private\n"


def test_df_rejects_home_wide_staging_and_outside_paths(home: Home) -> None:
    initialize(home)
    outside = home.path.parent / "outside"
    _ = outside.write_text("private\n")
    (home.path / "escape").symlink_to(outside)
    for value in (".", str(home.path), "../outside", str(outside), ".dotfiles.git", "escape"):
        result = command(home, "add", value)
        assert result.returncode != 0, value
    assert command(home, "add").returncode != 0
    assert not (home.path / ".dotfiles.git/index").exists()


def test_df_setup_plan_preserves_dirty_files_and_index(home: Home) -> None:
    initialize(home)
    result = command(home, "add", ".zshrc")
    assert result.returncode == 0, result.stderr
    assert command(home, "commit", "-m", "Fixture").returncode == 0
    _ = (home.path / ".zshrc").write_text("private edit\n")
    index = home.path / ".dotfiles.git/index"
    before = index.read_bytes()
    result = command(home, "setup", "plan", "--json")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["repository"] == str(home.path / ".dotfiles.git")
    assert plan["worktree"] == str(home.path)
    assert plan["origin"] == "git@github.com:amichne/dotfiles.git"
    assert ".zshrc" in plan["status"]
    assert index.read_bytes() == before
    assert (home.path / ".zshrc").read_text() == "private edit\n"


def test_df_rejects_missing_or_wrong_repository(home: Home) -> None:
    assert "missing-repository" in command(home, "status").stderr
    initialize(home)
    assert (
        git(home, "remote", "set-url", "origin", "git@github.com:someone/other.git").returncode == 0
    )
    result = command(home, "status")
    assert result.returncode != 0
    assert "unexpected-origin" in result.stderr
    assert (
        git(home, "remote", "set-url", "origin", "git@github.com:amichne/dotfiles.git").returncode
        == 0
    )
    assert git(home, "config", "core.bare", "false").returncode == 0
    assert "not-bare" in command(home, "status").stderr


def test_df_ignores_inherited_repository_selection(home: Home) -> None:
    initialize(home)
    home.env["GIT_DIR"] = str(home.path / "absent")
    home.env["GIT_WORK_TREE"] = str(home.path / "absent-worktree")
    home.env["GIT_INDEX_FILE"] = str(home.path / "other-index")
    assert command(home, "add", ".zprofile").returncode == 0
    assert not (home.path / "other-index").exists()
    del home.env["GIT_DIR"]
    del home.env["GIT_WORK_TREE"]
    del home.env["GIT_INDEX_FILE"]
    assert git(home, "diff", "--cached", "--name-only").stdout.splitlines() == [".zprofile"]


def test_df_passes_literal_paths_and_native_failures(home: Home) -> None:
    initialize(home)
    first = ".config/zsh/functions/literal*"
    _ = (home.path / first).write_text("one\n")
    _ = (home.path / ".config/zsh/functions/literal-other").write_text("two\n")
    assert command(home, "add", first).returncode == 0
    assert git(home, "diff", "--cached", "--name-only").stdout.splitlines() == [first]
    expected = git(home, "show", "missing-ref").returncode
    assert command(home, "git", "show", "missing-ref").returncode == expected != 0


def test_df_launcher_uses_home_source(home: Home) -> None:
    initialize(home)
    result = home.run(str(home.path / ".local/bin/df"), "setup", "plan", "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["worktree"] == str(home.path)


def test_public_inventory_ignores_private_and_generated_state(home: Home) -> None:
    initialize(home)
    for path in (
        ".ssh/id_ed25519",
        ".pi/agent/auth.json",
        ".pi/agent/sessions/example.jsonl",
        ".config/ayi/config.json",
        ".config/work/config.json",
        ".zshrc.local",
        "ayi/drafts/task",
        ".local/state/tool/data",
        ".dotfiles.git/index",
        ".codex/AGENTS.md",
        ".codex/hooks.json",
        ".pi/agent/AGENTS.md",
        ".pi/agent/extensions/private.ts",
    ):
        assert git(home, "check-ignore", path).returncode == 0, path
    for path in (
        ".zshrc",
        ".config/starship.toml",
        ".local/bin/keys",
        ".config/agent-engineering/B0.md",
    ):
        assert git(home, "check-ignore", path).returncode == 1, path


@pytest.mark.parametrize("ignored", [False, True])
def test_new_home_checkout_rejects_existing_conflicting_files(home: Home, ignored: bool) -> None:
    source = home.path.parent / "source"
    source.mkdir()
    _ = (source / ".zshrc").write_text("reviewed source\n")
    for args in (
        ["init", "--quiet", str(source)],
        ["-C", str(source), "add", ".zshrc"],
        [
            "-C",
            str(source),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "Fixture",
        ],
        ["clone", "--bare", str(source), str(home.path / ".dotfiles.git")],
    ):
        assert home.run("/usr/bin/git", *args).returncode == 0
    startup = home.path / ".zshrc"
    _ = startup.write_text("private existing file\n")
    if ignored:
        _ = (home.path / ".gitignore").write_text("*\n")
    result = git(home, "checkout", "--no-overwrite-ignore")
    assert result.returncode != 0
    assert startup.read_text() == "private existing file\n"
    startup.unlink()
    result = git(home, "checkout", "--no-overwrite-ignore")
    assert result.returncode == 0, result.stderr
    assert startup.read_text() == "reviewed source\n"
