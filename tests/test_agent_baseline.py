import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_user_scoped_guidance_routes_into_dotfiles_and_gates_itself() -> None:
    guidance = (ROOT / "AGENTS.md").read_text()
    assert len(guidance.split()) < 450
    repository_guide = ROOT / "docs/repository.md"
    assert "`docs/repository.md`" in guidance
    assert "writing.md" not in guidance
    assert "[writing guide](writing.md)" in repository_guide.read_text()
    assert "~/.dotfiles/" not in (ROOT / "docs/writing.md").read_text()


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
