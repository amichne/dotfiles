import os
import subprocess
from pathlib import Path

import pytest

from tests.test_main import SOURCE, git


@pytest.mark.parametrize("options", [(), ("--base", "alternate"), ("-b", "alternate")])
def test_feature(tmp_path: Path, options: tuple[str, ...]) -> None:
    remote = tmp_path / "remote"
    source = tmp_path / "source"
    checkout = tmp_path / "checkout"
    _ = git(tmp_path, "init", "--bare", str(remote))
    _ = git(tmp_path, "clone", str(remote), str(source))
    _ = git(source, "config", "user.email", "fixture@example.com")
    _ = git(source, "config", "user.name", "Fixture")
    _ = git(source, "switch", "-c", "main")
    _ = git(source, "commit", "--allow-empty", "-m", "initial")
    _ = git(source, "push", "origin", "main")
    _ = git(tmp_path, "clone", "-b", "main", str(remote), str(checkout))
    stale = git(checkout, "rev-parse", "HEAD")
    _ = git(checkout, "branch", "alternate")
    _ = git(source, "commit", "--allow-empty", "-m", "fresh remote tip")
    fresh = git(source, "rev-parse", "HEAD")
    _ = git(source, "push", "origin", "main")
    _ = (checkout / "untracked").write_text("keep")
    script = """
    wt() {
        [[ "$1" == switch && "$2" == --create && "$4" == --base ]] || return 42
        git worktree add -b "$3" "$DESTINATION" "$5" && cd "$DESTINATION"
    }
    fpath=("$SOURCE/.config/zsh/functions" $fpath)
    autoload -Uz feature
    feature "$@" && pwd -P
    """
    destination = tmp_path / "new-worktree"
    result = subprocess.run(
        ["zsh", "-f", "-c", script, "fixture", "new-feature", *options],
        cwd=checkout,
        env={**os.environ, "SOURCE": str(SOURCE), "DESTINATION": str(destination)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == str(destination.resolve())
    assert git(destination, "branch", "--show-current") == "new-feature"
    assert git(destination, "rev-parse", "HEAD") == (stale if options else fresh)
    assert git(checkout, "rev-parse", "HEAD") == stale
    assert (checkout / "untracked").read_text() == "keep"
