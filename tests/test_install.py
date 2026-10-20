from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import ROOT, Home

ORIGIN = "git@github.com:amichne/dotfiles.git"


def git(home: Home, directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return home.run("/usr/bin/git", "-C", str(directory), *args)


def commit(home: Home, source: Path, message: str) -> str:
    assert git(home, source, "add", "--all").returncode == 0
    result = git(
        home,
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--quiet",
        "-m",
        message,
    )
    assert result.returncode == 0, result.stderr
    return git(home, source, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def source(home: Home) -> Path:
    # Start with an empty destination. Never use the operator's HOME or credentials.
    for name in (".config", ".local", ".pi", "scripts"):
        shutil.rmtree(home.path / name)
    for name in (".gitignore", ".zshrc", ".zprofile"):
        (home.path / name).unlink()
    path = home.path.parent / "reviewed source ; literal"
    path.mkdir()
    assert git(home, path, "init", "--quiet", "--initial-branch=main").returncode == 0
    assert git(home, path, "remote", "add", "origin", ORIGIN).returncode == 0
    _ = (path / ".gitignore").write_text("*\n!/.zshrc\n!/.gitignore\n")
    _ = (path / ".zshrc").write_text("reviewed startup\n")
    _ = commit(home, path, "Initial source")
    return path


def run(home: Home, source: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return home.run(
        sys.executable, str(ROOT / "scripts/install.py"), "--source", str(source), *args
    )


def plan(home: Home, source: Path, *args: str) -> dict[str, object]:
    result = run(home, source, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def apply(home: Home, source: Path, *args: str) -> subprocess.CompletedProcess[str]:
    report = plan(home, source, *args)
    return run(home, source, *args, "--apply", "--expected-plan", str(report["planId"]))


def installed_git(home: Home, *args: str) -> subprocess.CompletedProcess[str]:
    return home.run(
        "/usr/bin/git",
        f"--git-dir={home.path / '.dotfiles.git'}",
        f"--work-tree={home.path}",
        *args,
    )


def test_plan_is_read_only_and_apply_uses_one_bare_index(home: Home, source: Path) -> None:
    before = sorted(home.path.iterdir())
    report = plan(home, source)
    assert report["action"] == "install"
    assert sorted(home.path.iterdir()) == before
    result = apply(home, source)
    assert result.returncode == 0, result.stderr
    assert (home.path / ".zshrc").read_text() == "reviewed startup\n"
    assert installed_git(home, "config", "core.bare").stdout.strip() == "true"
    assert installed_git(home, "remote", "get-url", "origin").stdout.strip() == ORIGIN
    assert (
        installed_git(home, "rev-parse", "HEAD").stdout
        == git(home, source, "rev-parse", "HEAD").stdout
    )
    assert installed_git(home, "status", "--porcelain", "--untracked-files=no").stdout == ""
    assert not (home.path / ".git").exists()
    index = home.path / ".dotfiles.git/index"
    index_before = index.read_bytes()
    assert plan(home, source)["action"] == "unchanged"
    assert index.read_bytes() == index_before


def test_changed_home_invalidates_the_plan_without_metadata_writes(
    home: Home, source: Path
) -> None:
    report = plan(home, source)
    _ = (home.path / ".zshrc").write_text("new conflict\n")
    result = run(home, source, "--apply", "--expected-plan", str(report["planId"]))
    assert result.returncode != 0 and "untracked-conflict" in result.stderr
    assert not (home.path / ".dotfiles.git").exists()
    assert (home.path / ".zshrc").read_text() == "new conflict\n"


def test_changed_untracked_file_stops_an_update(home: Home, source: Path) -> None:
    assert apply(home, source).returncode == 0
    (source / ".config").mkdir()
    _ = (source / ".config/new").write_text("public\n")
    assert git(home, source, "add", "--force", ".config/new").returncode == 0
    _ = commit(home, source, "New public file")
    (home.path / ".config").mkdir()
    _ = (home.path / ".config/new").write_text("private\n")
    result = run(home, source)
    assert "untracked-conflict" in result.stderr
    assert (home.path / ".config/new").read_text() == "private\n"


def test_update_preserves_private_files_and_rejects_dirty_work(home: Home, source: Path) -> None:
    assert apply(home, source).returncode == 0
    private = home.path / ".pi/agent/auth.json"
    private.parent.mkdir(parents=True)
    _ = private.write_text("private marker\n")
    _ = (source / ".zshrc").write_text("next startup\n")
    _ = commit(home, source, "Update")
    _ = (home.path / ".zshrc").write_text("local edit\n")
    result = run(home, source)
    assert result.returncode != 0 and "dirty-home" in result.stderr
    assert (home.path / ".zshrc").read_text() == "local edit\n"
    _ = (home.path / ".zshrc").write_text("reviewed startup\n")
    assert apply(home, source).returncode == 0
    assert (home.path / ".zshrc").read_text() == "next startup\n"
    assert private.read_text() == "private marker\n"


@pytest.mark.parametrize("kind", ["file", "ignored", "parent-symlink"])
def test_existing_untracked_files_and_symlinks_stop_before_writes(
    home: Home,
    source: Path,
    kind: str,
) -> None:
    outside = home.path.parent / "outside"
    if kind == "parent-symlink":
        outside.mkdir()
        (home.path / ".config").symlink_to(outside, target_is_directory=True)
        (source / ".config").mkdir()
        _ = (source / ".config/item").write_text("public\n")
        assert git(home, source, "add", "--force", ".config/item").returncode == 0
        _ = commit(home, source, "Config")
    else:
        _ = (home.path / ".zshrc").write_text("keep private\n")
        if kind == "ignored":
            _ = (home.path / ".gitignore").write_text("*\n")
    result = run(home, source)
    assert result.returncode != 0, result.stdout
    assert not (home.path / ".dotfiles.git").exists()
    if kind == "parent-symlink":
        assert not (outside / "item").exists()
    else:
        assert (home.path / ".zshrc").read_text() == "keep private\n"


def test_stale_plan_and_missing_plan_reject_application(home: Home, source: Path) -> None:
    old = plan(home, source)
    _ = (source / ".zshrc").write_text("new commit\n")
    _ = commit(home, source, "Changed source")
    result = run(home, source, "--apply", "--expected-plan", str(old["planId"]))
    assert result.returncode != 0 and "stale-plan" in result.stderr
    assert run(home, source, "--apply").returncode != 0
    assert not (home.path / ".dotfiles.git").exists()


def test_wrong_origin_and_divergent_history_are_rejected(home: Home, source: Path) -> None:
    assert apply(home, source).returncode == 0
    assert (
        installed_git(
            home, "remote", "set-url", "origin", "https://example.invalid/other"
        ).returncode
        == 0
    )
    assert "unexpected-origin" in run(home, source).stderr
    assert installed_git(home, "remote", "set-url", "origin", ORIGIN).returncode == 0
    _ = (home.path / ".zshrc").write_text("local commit\n")
    assert installed_git(home, "add", ".zshrc").returncode == 0
    assert (
        installed_git(
            home,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "Local",
        ).returncode
        == 0
    )
    assert "divergent-history" in run(home, source).stderr


def test_update_keeps_retired_private_append_and_a_backup(home: Home, source: Path) -> None:
    append = source / ".pi/agent/APPEND_SYSTEM.md"
    append.parent.mkdir(parents=True)
    _ = append.write_text("keep private append\n")
    assert git(home, source, "add", "--force", str(append)).returncode == 0
    _ = commit(home, source, "Old tracked append")
    # Model the previous installed release without asking the new installer to publish private input.
    assert (
        home.run(
            "/usr/bin/git", "clone", "--bare", str(source), str(home.path / ".dotfiles.git")
        ).returncode
        == 0
    )
    assert installed_git(home, "remote", "set-url", "origin", ORIGIN).returncode == 0
    assert installed_git(home, "checkout", "--no-overwrite-ignore").returncode == 0
    append.unlink()
    _ = commit(home, source, "Make append private")
    result = apply(home, source)
    assert result.returncode == 0, result.stderr
    assert (home.path / ".pi/agent/APPEND_SYSTEM.md").read_text() == "keep private append\n"
    assert installed_git(home, "ls-files", ".pi/agent/APPEND_SYSTEM.md").stdout == ""
    receipt = json.loads(result.stdout)
    backup = Path(receipt["backup"])
    assert (backup / "files/.pi/agent/APPEND_SYSTEM.md").read_text() == "keep private append\n"


def test_package_install_is_explicit_and_native_failure_is_reported(
    home: Home, source: Path
) -> None:
    log = home.path.parent / "pi.log"
    tool = home.tools / "pi"
    _ = tool.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$PI_LOG"\nexit 23\n')
    tool.chmod(0o755)
    home.env["PI_LOG"] = str(log)
    assert apply(home, source).returncode == 0
    assert not log.exists()
    result = apply(home, source, "--with-pi-subagents")
    assert result.returncode == 23
    assert log.read_text().splitlines() == ["install", "npm:pi-subagents@0.79.0"]
    assert json.loads(result.stdout)["status"] == "package-failed"
    assert (home.path / ".zshrc").read_text() == "reviewed startup\n"


def test_native_git_failure_keeps_preimages_and_its_exit_code(home: Home, source: Path) -> None:
    assert apply(home, source).returncode == 0
    _ = (source / ".zshrc").write_text("next startup\n")
    _ = commit(home, source, "Update")
    wrapper = home.tools / "git"
    _ = wrapper.write_text(
        '#!/bin/sh\nfor argument in "$@"; do\n'
        '  if [ "$argument" = merge ]; then exit 42; fi\ndone\n'
        'exec /usr/bin/git "$@"\n'
    )
    wrapper.chmod(0o755)
    result = apply(home, source)
    assert result.returncode == 42
    assert "git-failed:merge" in result.stderr
    assert "recovery-receipt:" in result.stderr
    assert (home.path / ".zshrc").read_text() == "reviewed startup\n"
    receipts = sorted((home.path / ".local/state/dotfiles-install").glob("apply-*/receipt.json"))
    failed = [
        path for path in receipts if json.loads(path.read_bytes())["status"] == "files-failed"
    ]
    assert len(failed) == 1
    assert (failed[0].parent / "files/.zshrc").read_text() == "reviewed startup\n"


def test_installer_rejects_dirty_source_and_inherited_git_selection(
    home: Home, source: Path
) -> None:
    home.env["GIT_DIR"] = str(home.path / "wrong-index")
    _ = (source / ".zshrc").write_text("uncommitted\n")
    result = run(home, source)
    assert result.returncode != 0 and "dirty-source" in result.stderr
    assert not (home.path / "wrong-index").exists()
    assert not (home.path / ".dotfiles.git").exists()


def test_candidate_symlinks_are_rejected(home: Home, source: Path) -> None:
    (source / ".zshrc").unlink()
    (source / ".zshrc").symlink_to("/outside")
    _ = commit(home, source, "Symlink")
    assert "unsupported-tree-entry" in run(home, source).stderr
    assert not (home.path / ".dotfiles.git").exists()


def test_candidate_private_instructions_are_rejected(home: Home, source: Path) -> None:
    target = source / ".pi/agent/APPEND_SYSTEM.md"
    target.parent.mkdir(parents=True)
    _ = target.write_text("private\n")
    assert git(home, source, "add", "--force", str(target)).returncode == 0
    _ = commit(home, source, "Private instructions")
    assert "private-source-path" in run(home, source).stderr
    assert not (home.path / ".dotfiles.git").exists()


def test_recovery_symlink_is_rejected_before_git_writes(home: Home, source: Path) -> None:
    outside = home.path.parent / "private state elsewhere"
    outside.mkdir()
    (home.path / ".local").mkdir()
    (home.path / ".local/state").symlink_to(outside, target_is_directory=True)
    assert "symlink-state" in run(home, source).stderr
    assert not (home.path / ".dotfiles.git").exists()
    assert list(outside.iterdir()) == []
