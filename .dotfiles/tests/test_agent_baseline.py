import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_user_scoped_guidance_routes_into_dotfiles_and_gates_itself() -> None:
    guidance = (ROOT / "AGENTS.md").read_text()
    assert len(guidance.split()) < 450
    for path in re.findall(r"`~/(\.dotfiles/[^`]+\.md)`", guidance):
        if path != ".dotfiles/controlled-english.md":
            assert (ROOT / path).is_file(), path
    assert "`~/.dotfiles/writing.md`" in guidance
    assert (ROOT / ".dotfiles/repository.md").is_file()
    assert "`.dotfiles/repository.md`" in guidance


def test_native_instruction_files_stay_private() -> None:
    git = ["git", "-C", str(ROOT)]
    selected = subprocess.run(
        [
            *git,
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            ".codex/AGENTS.md",
            ".claude/CLAUDE.md",
            ".pi/agent/AGENTS.md",
            ".codex/hooks.json",
            ".dotfiles/controlled-english.md",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert selected.stdout == ""
