import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_short_source_has_no_tracked_private_projections() -> None:
    source = (ROOT / ".config/agent-engineering/B0.md").read_bytes()
    git = ["git", "-C", str(ROOT)]
    if (ROOT / ".dotfiles.git").is_dir():
        git += [f"--git-dir={ROOT / '.dotfiles.git'}", f"--work-tree={ROOT}"]
    selected = subprocess.run(
        [
            *git,
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            ".codex/AGENTS.md",
            ".pi/agent/AGENTS.md",
            ".codex/hooks.json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert selected.stdout == ""
    assert source.count(b"# Engineering baseline B0") == 1
    assert len(source.split()) < 250
