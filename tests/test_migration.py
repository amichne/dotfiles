from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from .conftest import ORIGIN, Home, commit, git
from .test_layered_install import Installation

BASELINE = "cbe207a2585b05ebc9b738cb0574a98e3269fab8"
TARGETS = (".zshenv", ".zprofile", ".zshrc", ".config/git/config", ".config/starship.toml")
RETAINED = ".config/mise/config.toml"


@pytest.fixture
def legacy(home: Home, public_files: tuple[tuple[str, bytes, int], ...]) -> Installation:
    # Build a real legacy commit offline, then advance the ordinary checkout to the new installer.
    # The shared HOME fixture includes current assets. The bare revision predates this theme.
    (home.path / ".config/ghostty/themes/Neon Arcade").unlink()
    source = home.path / "dotfiles"
    source.mkdir()
    assert git(home, source, "init", "-q", "-b", "main").returncode == 0
    assert git(home, source, "remote", "add", "origin", ORIGIN).returncode == 0
    _ = (home.path / ".zshenv").write_text("export OLD_DOTFILES_ENV=1\n")
    for name in (*TARGETS, RETAINED):
        dst = source / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        _ = dst.write_bytes((home.path / name).read_bytes())
    _ = commit(home, source, "Original HOME configuration")
    result = home.run("git", "clone", "--bare", str(source), str(home.path / ".dotfiles.git"))
    assert result.returncode == 0, result.stderr
    assert git(home, home.path, "remote", "set-url", "origin", ORIGIN).returncode == 0
    assert git(home, home.path, "read-tree", "HEAD").returncode == 0
    del home.env["GIT_CONFIG_GLOBAL"]
    for name, content, mode in public_files:
        dst = source / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        _ = dst.write_bytes(content)
        dst.chmod(mode)
    _ = commit(home, source, "Reviewed layered installer")
    return Installation(home, source)


@pytest.fixture
def migration(legacy: Installation) -> Installation:
    # CI's public-file snapshot has no historical Git objects. Select its disposable commit
    # only in the fixture's copy of the program. The installed CLI has no baseline override.
    home = legacy.home
    revision = git(home, home.path, "rev-parse", "HEAD").stdout.strip()
    policy = legacy.source / "scripts/migration.py"
    original = policy.read_text()
    assert BASELINE in original
    _ = policy.write_text(original.replace(BASELINE, revision))
    _ = commit(home, legacy.source, "Select the synthetic baseline for this fixture")
    return legacy


def test_production_migration_refuses_other_revisions(legacy: Installation) -> None:
    result = legacy.run("--migrate")
    assert result.returncode != 0 and BASELINE in result.stderr
    assert (legacy.home.path / ".dotfiles.git").is_dir()
    assert (legacy.home.path / ".zshenv").read_text() == "export OLD_DOTFILES_ENV=1\n"


def test_migrate_preserves_other_files_and_archives_git(migration: Installation) -> None:
    home = migration.home
    revision = git(home, home.path, "rev-parse", "HEAD").stdout.strip()
    state = home.path / ".local/state/dotfiles-install"
    private = home.path / ".zshrc.local"
    _ = private.write_text("export USER_SETTING=local\n")
    retained = (home.path / RETAINED).read_bytes()
    before = {name: (home.path / name).read_bytes() for name in TARGETS}
    plan = migration.plan("--migrate")
    assert (home.path / ".dotfiles.git").is_dir() and not state.exists()
    assert {name: (home.path / name).read_bytes() for name in TARGETS} == before
    result = migration.run("--migrate", "--apply", "--expected-plan", str(plan["planId"]))
    assert result.returncode == 0, result.stderr
    report: dict[str, object] = json.loads(result.stdout)
    archive = Path(str(report["archivedRepository"]))
    assert archive.is_dir() and not (home.path / ".dotfiles.git").exists()
    assert home.run("git", f"--git-dir={archive}", "rev-parse", "HEAD").stdout.strip() == revision
    assert (home.path / ".config/starship.toml").readlink() == migration.source / TARGETS[-1]
    assert b"OLD_DOTFILES_ENV" not in (home.path / ".zshenv").read_bytes()
    assert (
        home.run("git", "config", "--get", "alias.root").stdout.strip()
        == "rev-parse --show-toplevel"
    )
    shell = home.run("/bin/zsh", "-dc", 'print -r -- "$WORKTREE_ROOT"')
    assert shell.returncode == 0 and shell.stdout.strip() == str(home.path / ".worktrees")
    ghostty = home.path / ".config/ghostty/config.ghostty"
    theme = migration.source / ".config/ghostty/themes/Neon Arcade"
    shader = migration.source / ".config/ghostty/cursor-trail.glsl"
    editor = home.path / ".config/nvim/init.lua"
    assert migration.run().returncode != 0
    assert editor.is_file() and not editor.is_symlink()
    _ = editor.rename(editor.with_suffix(".lua.personal"))
    assert migration.plan()["changes"] == [
        {
            "path": str(ghostty.parent / "themes/Neon Arcade"),
            "operation": "link",
            "source": str(theme),
            "block": None,
        },
        {
            "path": str(ghostty),
            "operation": "block",
            "source": str(shader),
            "block": (
                f"# >>> amichne/dotfiles >>>\ntheme = Neon Arcade\ncustom-shader = {shader}\n"
                "# <<< amichne/dotfiles <<<\n"
            ),
        },
        {
            "path": str(editor),
            "operation": "link",
            "source": str(migration.source / ".config/nvim/init.lua"),
            "block": None,
        },
    ]
    migration.apply()
    assert ghostty.is_file() and migration.plan()["changes"] == []
    migration.apply("--uninstall")
    assert not ghostty.exists()
    assert not (home.path / ".config/starship.toml").is_symlink()
    assert private.read_text() == "export USER_SETTING=local\n"
    assert (home.path / RETAINED).read_bytes() == retained
    assert archive.is_dir()


def test_interrupted_migration_resumes_without_discarding_local_edits(
    migration: Installation,
) -> None:
    home = migration.home
    plan_id = str(migration.plan("--migrate")["planId"])
    program = """
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import install
metadata = Path.home() / ".dotfiles.git"
def interrupt_archive(action):
    def call(src, dst, **kwargs):
        if Path(src) == metadata:
            os._exit(75)
        return action(src, dst, **kwargs)
    return call
os.rename = interrupt_archive(os.rename)
os.replace = interrupt_archive(os.replace)
sys.argv = ["install.py", "--layered", "--migrate", "--apply", "--expected-plan", sys.argv[2]]
sys.exit(install.main())
"""
    stop = home.run(sys.executable, "-c", program, str(migration.source / "scripts"), plan_id)
    assert stop.returncode == 75, stop.stderr
    assert (home.path / ".dotfiles.git").is_dir()
    assert (home.path / ".config/starship.toml").is_symlink()
    assert migration.run().returncode != 0
    hook = home.path / ".zshrc"
    installed = hook.read_bytes()
    edited = installed + b"# concurrent personal edit\n"
    _ = hook.write_bytes(edited)
    rejected = migration.run("--migrate")
    assert rejected.returncode != 0 and rejected.stderr
    assert hook.read_bytes() == edited and (home.path / ".dotfiles.git").is_dir()
    _ = hook.write_bytes(installed)
    migration.apply("--migrate")
    migration.apply("--uninstall")
    assert not (home.path / ".config/ghostty/config.ghostty").exists()
    assert not (home.path / ".dotfiles.git").exists()


@pytest.mark.parametrize(
    "kind",
    ["staged", "hidden-change", "unstaged", "symlink", "custom-root", "source-advanced", "origin"],
)
def test_changed_baseline_blocks_apply(migration: Installation, kind: str) -> None:
    home = migration.home
    plan_id = str(migration.plan("--migrate")["planId"])
    shell = home.path / ".zshrc"
    if kind == "staged":
        _ = shell.write_text("# staged change\n")
        assert git(home, home.path, "add", "--", ".zshrc").returncode == 0
    elif kind == "hidden-change":
        assert git(home, home.path, "update-index", "--assume-unchanged", ".zshrc").returncode == 0
        _ = shell.write_text("# personal override\n")
    elif kind == "unstaged":
        _ = (home.path / RETAINED).write_text("# unrelated tracked change\n")
    elif kind == "symlink":
        shell.unlink()
        shell.symlink_to(migration.source / ".zshrc")
    elif kind == "custom-root":
        home.env["ZDOTDIR"] = str(home.path / "other shell root")
    elif kind == "source-advanced":
        _ = (migration.source / ".zshenv").write_text("# updated configuration\n")
        _ = commit(home, migration.source, "Advance checkout after preview")
    else:
        assert git(home, home.path, "remote", "set-url", "origin", "other").returncode == 0
    expected = {name: (home.path / name).read_bytes() for name in (*TARGETS, RETAINED)}
    index = home.path / ".dotfiles.git/index"
    index_before = index.read_bytes()
    result = migration.run("--migrate", "--apply", "--expected-plan", plan_id)
    assert result.returncode != 0 and result.stderr
    assert (home.path / ".dotfiles.git").is_dir()
    assert index.read_bytes() == index_before
    assert {name: (home.path / name).read_bytes() for name in expected} == expected
    assert not (home.path / ".config/starship.toml").is_symlink()
