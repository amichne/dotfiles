import os
import subprocess
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2]


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


@pytest.mark.parametrize("mode", ["dirty", "clean", "pull-failure", "conflict", "switch-fallback"])
def test_main(tmp_path: Path, mode: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    remote = tmp_path / "remote"
    target = tmp_path / "target"
    feature = tmp_path / "feature"
    _ = git(tmp_path, "init", "--bare", str(remote))
    _ = git(tmp_path, "clone", str(remote), str(target))
    _ = git(target, "config", "user.email", "fixture@example.com")
    _ = git(target, "config", "user.name", "Fixture")
    _ = git(target, "checkout", "-b", "main")
    _ = (target / "file").write_text("base\n")
    _ = git(target, "add", "file")
    _ = git(target, "commit", "-m", "base")
    _ = git(target, "push", "origin", "main")
    _ = git(target, "worktree", "add", "-b", "feature", str(feature))
    _ = (target / "old").write_text("old stash")
    _ = git(target, "stash", "push", "-u", "-m", "existing")
    old_stash = git(target, "rev-parse", "refs/stash")
    if mode in {"dirty", "clean"}:
        _ = (feature / "remote-file").write_text("remote update")
        _ = git(feature, "add", "remote-file")
        _ = git(feature, "commit", "-m", "remote update")
        _ = git(feature, "push", "origin", "HEAD:main")
    if mode == "conflict":
        _ = (feature / "file").write_text("remote\n")
        _ = git(feature, "commit", "-am", "remote")
        _ = git(feature, "push", "origin", "HEAD:main")
        _ = (target / "file").write_text("local\n")
    elif mode != "clean":
        _ = (target / "staged").write_text("staged")
        _ = git(target, "add", "staged")
        _ = (target / "untracked").write_text("untracked")
        _ = (target / "file").write_text("local\n")
    if mode == "switch-fallback":
        _ = git(target, "switch", "-c", "fallback-source")
    if mode == "pull-failure":
        _ = git(target, "remote", "set-url", "origin", str(tmp_path / "missing"))
    _ = (feature / "feature-dirt").write_text("keep")
    # Only the parent-shell worktree switch is a fake. Git effects are real.
    script = """
    wt() { [[ "$MODE" != switch-fallback ]] || return 42; [[ "$1" == switch && "$2" == main ]] || return 42; cd "$TARGET"; }
    fpath=("$SOURCE/.config/zsh/functions" $fpath)
    autoload -Uz main
    main
    """
    result = subprocess.run(
        ["zsh", "-f", "-c", script],
        cwd=target if mode == "switch-fallback" else feature,
        env={**env, "SOURCE": str(SOURCE), "TARGET": str(target), "MODE": mode},
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) == (mode in {"dirty", "clean", "switch-fallback"}), (
        result.stderr
    )
    if mode == "switch-fallback":
        assert git(target, "branch", "--show-current") == "main"
    assert (feature / "feature-dirt").read_text() == "keep"
    if mode in {"dirty", "clean"}:
        assert (target / "remote-file").read_text() == "remote update"
    if mode == "conflict":
        assert git(target, "diff", "--name-only", "--diff-filter=U") == "file"
        assert git(target, "stash", "list").count("\n") == 1
    else:
        assert git(target, "rev-parse", "refs/stash") == old_stash
        if mode != "clean":
            assert (target / "file").read_text() == "local\n"
            assert (target / "untracked").read_text() == "untracked"
            assert git(target, "diff", "--cached", "--name-only") == "staged"
