from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .conftest import Home
from .test_worktree_inventory import command, repository, worktree

OLD = time.time() - 10 * 86400
NO_DAEMON = "no-such-daemon-process-for-reclaim-tests"


def age(checkout: Path) -> None:
    git_dir = checkout.parent / "repository with spaces" / ".git" / "worktrees" / checkout.name
    for name in ("index", "HEAD", "logs/HEAD"):
        if (git_dir / name).exists():
            os.utime(git_dir / name, (OLD, OLD))


def output(checkout: Path) -> Path:
    build = checkout / "build" / "classes"
    build.mkdir(parents=True)
    _ = (build / "A.class").write_bytes(b"x" * 8192)
    return checkout / "build"


def config(home: Home, **extra: object) -> Path:
    path = home.path.parent / "reclaim.toml"
    lines = [
        f'daemon_pattern = "{NO_DAEMON}"',
        f'patch_root = "{home.path.parent / "patches"}"',
        'base_ref = "main"',
    ]
    lines += [f"{key} = {json.dumps(value)}" for key, value in extra.items()]
    _ = path.write_text("\n".join(lines) + "\n")
    return path


def reclaim(home: Home, root: Path, settings: Path, *args: str) -> dict[str, object]:
    result = command(
        home, "reclaim", "--repo", str(root), "--config", str(settings), "--json", *args
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def rows(report: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["path"]: row for row in report["worktrees"]}  # type: ignore[union-attr,index,misc]


def test_plan_lists_build_output_without_deleting(home: Home) -> None:
    root = repository(home)
    _ = home.run("/usr/bin/git", "-C", str(root), "branch", "-M", "main")
    checkout = worktree(home, root, "idle")
    build = output(checkout)
    _ = output(root)
    report = reclaim(home, root, config(home))
    found = rows(report)
    assert found[str(root)]["retained"] == "main-worktree"
    assert [t["path"] for t in found[str(checkout)]["targets"]] == [str(build)]  # type: ignore[union-attr,index]
    assert found[str(checkout)]["needsPatch"] is False
    assert report["daemonsRunning"] is False
    assert build.is_dir()


def test_apply_saves_changes_as_patch_before_removing_build(home: Home) -> None:
    root = repository(home)
    _ = home.run("/usr/bin/git", "-C", str(root), "branch", "-M", "main")
    checkout = worktree(home, root, "changed")
    build = output(checkout)
    _ = (checkout / "source.txt").write_text("edited\n")
    _ = (checkout / "new.txt").write_text("fresh\n")
    age(checkout)
    report = reclaim(home, root, config(home), "--apply")
    row = rows(report)[str(checkout)]
    assert row["action"] == "removed-build"
    saved = Path(str(row["patch"]))
    patch = (saved / "worktree.patch").read_text()
    assert "+edited" in patch and "+fresh" in patch
    assert json.loads((saved / "meta.json").read_text())["branch"] == "changed"
    assert not build.exists()
    assert (checkout / "source.txt").read_text() == "edited\n"


def test_unsaved_changes_are_retained_when_patching_is_off(home: Home) -> None:
    root = repository(home)
    checkout = worktree(home, root, "changed")
    _ = output(checkout)
    _ = (checkout / "source.txt").write_text("edited\n")
    report = reclaim(home, root, config(home, patch_changed=False), "--apply")
    assert rows(report)[str(checkout)]["retained"] == "changed-unsaved"
    assert (checkout / "build").is_dir()


def test_invalid_config_and_missing_repository_are_rejected(home: Home) -> None:
    bad = home.path.parent / "bad.toml"
    _ = bad.write_text("idle_days = -1\n")
    root = repository(home)
    assert command(home, "reclaim").returncode == 64
    result = command(home, "reclaim", "--repo", str(root), "--config", str(bad))
    assert result.returncode == 64
    assert "invalid-config" in result.stderr


def test_same_named_worktrees_get_separate_patches(home: Home) -> None:
    root = repository(home)
    _ = home.run("/usr/bin/git", "-C", str(root), "branch", "-M", "main")
    checkouts: list[Path] = []
    for parent in ("first", "second"):
        path = home.path.parent / parent / "kast"
        path.parent.mkdir()
        result = home.run(
            "/usr/bin/git", "-C", str(root), "worktree", "add", "-b", parent, str(path)
        )
        assert result.returncode == 0, result.stderr
        _ = output(path)
        _ = (path / "source.txt").write_text(f"{parent}\n")
        checkouts.append(path)
    report = reclaim(home, root, config(home), "--apply")
    found = rows(report)
    patches = {str(found[str(path)]["patch"]) for path in checkouts}
    assert len(patches) == 2
    assert all(found[str(path)]["action"] == "removed-build" for path in checkouts)


def test_repository_named_twice_lists_each_worktree_once(home: Home) -> None:
    root = repository(home)
    checkout = worktree(home, root, "child")
    result = command(
        home,
        "reclaim",
        "--repo",
        str(root),
        "--repo",
        str(checkout),
        "--config",
        str(config(home)),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    paths = [row["path"] for row in json.loads(result.stdout)["worktrees"]]
    assert sorted(paths) == sorted({str(root), str(checkout)})
