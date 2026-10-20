from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

from .conftest import Home

ROOT = Path(__file__).resolve().parents[1]


def test_home_source_contains_the_requested_public_files() -> None:
    for name in (".zshrc", ".zprofile", ".local/bin/keys", ".local/bin/shell-prompt"):
        assert (ROOT / name).is_file(), name
    for name in ("keys", "shell-prompt"):
        assert os.access(ROOT / ".local/bin" / name, os.X_OK)
    assert {p.name for p in (ROOT / ".config").iterdir()} == {
        "agent-engineering",
        "atuin",
        "mise",
        "nvim",
        "prompt.json",
        "shell-prompt",
        "starship.toml",
        "yazi",
        "zsh",
    }
    assert {str(p.relative_to(ROOT / ".pi")) for p in (ROOT / ".pi").rglob("*") if p.is_file()} == {
        "agent/agents/researcher.md",
        "agent/agents/scout.md",
        "agent/agents/worker.md",
        "agent/pi-lsp.json",
        "agent/prompts/verify.md",
    }


def test_repository_contains_only_current_source_owners() -> None:
    git = ["git", "-C", str(ROOT)]
    if (ROOT / ".dotfiles.git").is_dir():
        git = ["git", f"--git-dir={ROOT / '.dotfiles.git'}", f"--work-tree={ROOT}"]
    result = subprocess.run(
        [*git, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    roots = {Path(p).parts[0] for p in result.stdout.split("\0") if p and (ROOT / p).exists()}
    assert roots == {
        ".config",
        ".github",
        ".gitignore",
        ".local",
        ".pi",
        ".python-version",
        ".zprofile",
        ".zshrc",
        "AGENTS.md",
        "README.md",
        "containers",
        "docs",
        "pyproject.toml",
        "scripts",
        "tests",
        "uv.lock",
        "zensical.toml",
    }


def prepare_integrations(home: Home) -> Path:
    log = home.path / "integrations.log"
    home.env["INTEGRATION_LOG"] = str(log)
    for name in ("mise", "atuin", "zoxide", "wt", "starship"):
        tool = home.tools / name
        _ = tool.write_text(
            '#!/bin/sh\nprintf "%s" "${0##*/}" >> "$INTEGRATION_LOG"\n'
            'printf " %s" "$@" >> "$INTEGRATION_LOG"\n'
            'printf "\\n" >> "$INTEGRATION_LOG"\nprintf ":\\n"\n',
            encoding="utf-8",
        )
        tool.chmod(0o755)
    plugins = home.path / "system plugins"
    for name in ("zsh-autosuggestions", "zsh-syntax-highlighting"):
        directory = plugins / name
        directory.mkdir(parents=True)
        _ = (directory / f"{name}.zsh").write_text(
            f'print -r -- "{name}" >> "$INTEGRATION_LOG"\n', encoding="utf-8"
        )
    home.env["ZSH_PLUGIN_ROOT"] = str(plugins)
    return log


def test_fresh_interactive_shell_loads_the_direct_source_once(home: Home) -> None:
    log = prepare_integrations(home)
    result = home.run(
        "/bin/zsh",
        "-d",
        "-i",
        "-c",
        'source "$HOME/.zshrc"; print -r -- "result=$_SHELL_CONFIG_RESULT"; '
        'print -r -- "$EDITOR"; whence f rr y; bindkey "^W"',
    )
    assert result.returncode == 0, result.stderr
    assert "result=0" in result.stdout
    assert "nvim" in result.stdout
    assert "backward-kill-word" in result.stdout
    for name in ("f", "rr", "y"):
        assert name in result.stdout.splitlines()
    assert log.read_text().splitlines() == [
        "mise activate zsh",
        "mise completion zsh",
        "atuin gen-completions --shell zsh",
        "zoxide init zsh",
        "wt config shell init zsh",
        "atuin init zsh --disable-up-arrow",
        "starship init zsh",
        "zsh-autosuggestions",
        "zsh-syntax-highlighting",
    ]


def test_fuzzy_search_excludes_bare_git_metadata(home: Home) -> None:
    _ = prepare_integrations(home)
    result = home.run(
        "/bin/zsh",
        "-d",
        "-i",
        "-c",
        'print -rl -- "$FZF_DEFAULT_COMMAND" "$FZF_ALT_C_COMMAND"',
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "fd --type f --hidden --exclude .git --exclude .dotfiles.git",
        "fd --type d --hidden --exclude .git --exclude .dotfiles.git",
    ]


def test_fzf_preview_command_is_one_option(home: Home) -> None:
    _ = prepare_integrations(home)
    result = home.run("/bin/zsh", "-d", "-i", "-c", 'print -r -- "$FZF_CTRL_T_OPTS"')
    assert result.returncode == 0, result.stderr
    assert shlex.split(result.stdout) == [
        "--preview",
        "bat --color=always --style=numbers --line-range=:200 -- {}",
        "--preview-window=right:50%",
    ]


def test_fzf_preview_preserves_custom_options(home: Home) -> None:
    _ = prepare_integrations(home)
    options = "--preview 'head -n 20 -- {}' --preview-window=bottom:30%"
    home.env["FZF_CTRL_T_OPTS"] = options
    result = home.run("/bin/zsh", "-d", "-i", "-c", 'print -r -- "$FZF_CTRL_T_OPTS"')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == options


def test_missing_shell_dependency_returns_failure(home: Home) -> None:
    _ = prepare_integrations(home)
    (home.tools / "atuin").unlink()
    result = home.run("/bin/zsh", "-d", "-i", "-c", 'return "$_SHELL_CONFIG_RESULT"')
    assert result.returncode == 127
    assert "stage=atuin outcome=missing-command" in result.stderr


def test_login_shell_only_prepares_paths(home: Home) -> None:
    log = prepare_integrations(home)
    result = home.run("/bin/zsh", "-d", "-l", "-c", 'print -rl -- "$path[@]"')
    assert result.returncode == 0, result.stderr
    assert str(home.path / ".local/bin") in result.stdout.splitlines()
    assert str(home.path / ".local/share/mise/shims") in result.stdout.splitlines()
    assert not log.exists()


def test_keys_runs_without_the_removed_toolbox(home: Home) -> None:
    result = home.run(str(home.path / ".local/bin/keys"), "--json")
    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert {row["tool"] for row in rows} == {"shell", "yazi"}
    assert any(row["key"] == "Ctrl-R" for row in rows)
    result = home.run(str(home.path / ".local/bin/keys"), "unknown", "--list")
    assert result.returncode == 2


def test_keys_rejects_invalid_editor_maps(home: Home) -> None:
    tool = home.tools / "nvim"
    _ = tool.write_text('#!/bin/sh\nprintf \'[{"key":42,"description":"bad"}]\'\n')
    tool.chmod(0o755)
    result = home.run(str(home.path / ".local/bin/keys"), "nvim", "--json")
    assert result.returncode == 2
    assert "INVALID_MAPS" in result.stderr


def test_prompt_launcher_uses_the_direct_source(home: Home) -> None:
    assert (home.tools / "node").exists(), "Run scripts/check.sh to resolve the Node executable"
    result = home.run(str(home.path / ".local/bin/shell-prompt"), "context", "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"kind": "outside"}
    result = home.run(
        str(home.path / ".local/bin/shell-prompt"), "context", "--settings", "invalid"
    )
    assert result.returncode == 2
    assert "stage=settings outcome=invalid" in result.stderr
