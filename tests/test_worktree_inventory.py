from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from .conftest import Home
from .test_df import command


def repository(home: Home) -> Path:
    root = home.path.parent / "repository with spaces"
    root.mkdir()
    for args in (
        ("init", "--quiet", str(root)),
        ("-C", str(root), "config", "user.name", "Fixture"),
        ("-C", str(root), "config", "user.email", "fixture@example.invalid"),
    ):
        result = home.run("/usr/bin/git", *args)
        assert result.returncode == 0, result.stderr
    _ = (root / "source.txt").write_text("original\n")
    _ = (root / ".gitignore").write_text("build/\n")
    for args in (("add", "."), ("commit", "--quiet", "-m", "Fixture")):
        result = home.run("/usr/bin/git", "-C", str(root), *args)
        assert result.returncode == 0, result.stderr
    return root


def worktree(home: Home, root: Path, name: str) -> Path:
    path = home.path.parent / name
    result = home.run("/usr/bin/git", "-C", str(root), "worktree", "add", "-b", name, str(path))
    assert result.returncode == 0, result.stderr
    return path


def test_inventory_reports_registered_worktrees_without_home_repository(home: Home) -> None:
    root = repository(home)
    checkout = worktree(home, root, "child")
    before = (root / ".git/index").read_bytes()
    result = command(home, "worktrees", "--repo", str(root), "--json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["version"] == 1
    assert report["status"] == "complete"
    assert {row["path"] for row in report["repositories"][0]["worktrees"]} == {
        str(root),
        str(checkout),
    }
    for row in report["repositories"][0]["worktrees"]:
        assert row["decision"] == "retain"
        assert row["workingState"]["kind"] == "clean"
        assert "activity-unproved" in row["reasons"]
        assert "delivery-unproved" in row["reasons"]
    assert (root / ".git/index").read_bytes() == before
    assert not (home.path / ".dotfiles.git").exists()


def test_inventory_preserves_dirty_untracked_locked_and_missing(home: Home) -> None:
    root = repository(home)
    dirty = worktree(home, root, "dirty")
    locked = worktree(home, root, "locked")
    missing = worktree(home, root, "missing")
    result = home.run(
        "/usr/bin/git", "-C", str(root), "worktree", "lock", "--reason", "keep", str(locked)
    )
    assert result.returncode == 0, result.stderr
    _ = (dirty / "source.txt").write_text("local edit\n")
    _ = (dirty / "untracked.txt").write_text("uncommitted\n")
    shutil.rmtree(missing)
    before = home.run(
        "/usr/bin/git", "-C", str(root), "worktree", "list", "--porcelain", "-z"
    ).stdout
    result = command(home, "worktrees", "--repo", str(root), "--json")
    assert result.returncode == 0, result.stderr
    rows = {row["path"]: row for row in json.loads(result.stdout)["repositories"][0]["worktrees"]}
    assert rows[str(dirty)]["workingState"] == {
        "kind": "changed",
        "tracked": True,
        "untracked": True,
    }
    assert {"dirty", "untracked"}.issubset(rows[str(dirty)]["reasons"])
    assert "locked" in rows[str(locked)]["reasons"]
    assert {"missing", "prunable"}.issubset(rows[str(missing)]["reasons"])
    assert rows[str(missing)]["workingState"]["kind"] == "unavailable"
    assert all(row["decision"] == "retain" for row in rows.values())
    assert (dirty / "source.txt").read_text() == "local edit\n"
    assert (dirty / "untracked.txt").read_text() == "uncommitted\n"
    assert (
        home.run("/usr/bin/git", "-C", str(root), "worktree", "list", "--porcelain", "-z").stdout
        == before
    )


def test_inventory_rejects_missing_repository_and_preserves_other_results(home: Home) -> None:
    root = repository(home)
    result = command(
        home, "worktrees", "--repo", str(root), "--repo", str(root / "absent"), "--json"
    )
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "incomplete"
    assert report["repositories"][0]["status"] == "complete"
    assert report["repositories"][1]["failure"] == "git-failed"


def test_inventory_limit_is_explicit_and_never_claims_complete(home: Home) -> None:
    root = repository(home)
    _ = worktree(home, root, "child")
    config = home.path / "limits.toml"
    _ = config.write_text("max_worktrees = 1\ntimeout_seconds = 10\n")
    result = command(home, "worktrees", "--repo", str(root), "--config", str(config), "--json")
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "incomplete"
    assert report["repositories"][0]["failure"] == "worktree-limit"
    assert len(report["repositories"][0]["worktrees"]) == 1


def test_inventory_ignores_inherited_git_selection(home: Home) -> None:
    root = repository(home)
    home.env["GIT_DIR"] = str(root / "absent")
    home.env["GIT_WORK_TREE"] = str(root / "wrong")
    home.env["GIT_INDEX_FILE"] = str(root / "wrong-index")
    result = command(home, "worktrees", "--repo", str(root), "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["repositories"][0]["worktrees"][0]["path"] == str(root)
    assert not (root / "wrong-index").exists()


def test_inventory_has_no_implicit_repository_or_write_mode(home: Home) -> None:
    for args in (("worktrees", "--json"), ("worktrees", "--repo", str(home.path), "--delete")):
        result = command(home, *args)
        assert result.returncode == 64


def test_inventory_reports_unknown_worktree_state_without_pruning(home: Home) -> None:
    root = repository(home)
    checkout = worktree(home, root, "unreadable")
    (checkout / ".git").unlink()
    result = command(home, "worktrees", "--repo", str(root), "--json")
    assert result.returncode != 0
    report = json.loads(result.stdout)
    row = next(
        row for row in report["repositories"][0]["worktrees"] if row["path"] == str(checkout)
    )
    assert row["decision"] == "retain"
    assert row["workingState"] == {"kind": "unavailable", "reason": "git-failed"}
    assert checkout.exists()


def test_inventory_rejects_invalid_limits_before_git(home: Home) -> None:
    config = home.path / "limits.toml"
    for data in (
        "max_worktrees = 0\ntimeout_seconds = 10\n",
        "max_worktrees = true\ntimeout_seconds = 10\n",
        "max_worktrees = 2\ntimeout_seconds = 10\nremove = true\n",
    ):
        _ = config.write_text(data)
        result = command(
            home, "worktrees", "--repo", str(home.path), "--config", str(config), "--json"
        )
        assert result.returncode != 0
        assert json.loads(result.stdout)["failure"] == "invalid-config"


def test_inventory_shared_deadline_stops_slow_git(home: Home) -> None:
    # This process adapter substitutes delay only, not worktree or status evidence.
    executable = home.tools / "git"
    _ = executable.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(5)\n")
    executable.chmod(0o755)
    config = home.path / "limits.toml"
    _ = config.write_text("max_worktrees = 2\ntimeout_seconds = 1\n")
    result = command(
        home,
        "worktrees",
        "--repo",
        str(home.path),
        "--repo",
        str(home.tools),
        "--config",
        str(config),
        "--json",
    )
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "incomplete"
    assert [row["failure"] for row in report["repositories"]] == [
        "deadline-exceeded",
        "deadline-exceeded",
    ]
