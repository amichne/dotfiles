from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest

from .conftest import ORIGIN, Home, commit, git
from .test_home_source import prepare_integrations


@dataclass(frozen=True)
class Installation:
    home: Home
    source: Path

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self.home.run(str(self.source / "install.sh"), *args)

    def plan(self, *args: str) -> dict[str, object]:
        result = self.run(*args)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def apply(self, *args: str) -> None:
        plan_id = self.plan(*args)["planId"]
        result = self.run(*args, "--apply", "--expected-plan", str(plan_id))
        assert result.returncode == 0, result.stderr


def test_two_applies_use_one_reviewed_plan(installation: Installation) -> None:
    plan_id = str(installation.plan()["planId"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = [
            pool.submit(installation.run, "--apply", "--expected-plan", plan_id) for _ in range(2)
        ]
    results = [run.result() for run in runs]
    assert sorted(result.returncode for result in results) == [0, 65]
    assert any("stale-plan" in result.stderr for result in results)
    assert installation.plan()["changes"] == []


def test_partial_apply_can_resume_and_remove(installation: Installation) -> None:
    home = installation.home
    local = home.path / ".zshenv"
    original = b"# personal environment\n"
    _ = local.write_bytes(original)
    plan_id = str(installation.plan()["planId"])
    # Use a new process. Interrupt after the first real hook write with the apply lock held.
    program = """
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import install, layered
write = layered.write
def interrupted(path, *args):
    write(path, *args)
    if path == Path.home() / ".zshenv":
        os._exit(75)
layered.write = interrupted
sys.argv = ["install.py", "--layered", "--apply", "--expected-plan", sys.argv[2]]
sys.exit(install.main())
"""
    stopped = home.run(sys.executable, "-c", program, str(installation.source / "scripts"), plan_id)
    assert stopped.returncode == 75, stopped.stderr
    assert local.read_bytes() != original and not (home.path / ".zshrc").exists()
    (recovery,) = (home.path / ".local/state/dotfiles-install").glob("layered-*/receipt.json")
    assert (recovery.parent / "0").read_bytes() == original
    installation.apply()
    assert installation.plan()["changes"] == []
    installation.apply("--uninstall")
    assert local.read_bytes() == original


@pytest.fixture
def installation(home: Home, public_files: tuple[tuple[str, bytes, int], ...]) -> Installation:
    # The standard fixture has a full HOME deployment. Use its isolated tools with a fresh HOME.
    path = home.path.parent / "new home"
    path.mkdir()
    env = home.env | {"HOME": str(path)}
    for key in ("ZDOTDIR", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        del env[key]
    del env["GIT_CONFIG_GLOBAL"]
    clean_home = Home(path, home.tools, env)
    source = path / """checkout's "$" files"""
    source.mkdir()
    for name, contents, mode in public_files:
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        _ = file.write_bytes(contents)
        file.chmod(mode)
    assert git(clean_home, source, "init", "--quiet", "--initial-branch=main").returncode == 0
    assert git(clean_home, source, "remote", "add", "origin", ORIGIN).returncode == 0
    _ = commit(clean_home, source, "Public source")
    return Installation(clean_home, source)


def test_direct_installer_defaults_to_the_checkout_layer(installation: Installation) -> None:
    script = installation.source / "scripts/install.py"
    home = installation.home
    result = home.run("uv", "run", "--locked", "--script", str(script))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == installation.plan()
    for option in ("--with-pi-subagents", "--without-slopsentral"):
        assert installation.run(option).returncode == 2
    assert not (home.path / ".dotfiles.git").exists()


def test_empty_home_install_round_trip(installation: Installation) -> None:
    home = installation.home.path
    starship = home / ".config/starship.toml"
    assert installation.plan()["changes"]
    assert not (home / ".zshrc").exists()
    assert not starship.exists()
    installation.apply()
    settings = home / ".config/dotfiles/config.toml"
    assert tomllib.loads(settings.read_text()) == {
        "ai": {
            "provider": "codex",
            "recent": 3,
            "codex": {"flags": []},
            "copilot": {"flags": []},
            "claude": {"flags": []},
        }
    }
    assert settings.stat().st_mode & 0o777 == 0o600
    assert not (installation.source / ".config-backups").exists()
    assert starship.is_symlink()
    assert starship.resolve() == installation.source / ".config/starship.toml"
    editor = home / ".config/nvim/init.lua"
    assert editor.readlink() == installation.source / ".config/nvim/init.lua"
    config = home / ".config/ghostty/config.ghostty"
    theme = config.parent / "themes/Neon Arcade"
    assert theme.readlink() == installation.source / ".config/ghostty/themes/Neon Arcade"
    assert config.read_text().splitlines()[1] == "theme = Neon Arcade"
    assert not (home / ".config").is_symlink()
    assert not (home / ".dotfiles.git").exists()
    assert installation.plan()["changes"] == []
    installation.apply("--uninstall")
    assert not starship.is_symlink()
    assert settings.exists()
    assert not editor.is_symlink()
    assert not config.exists()
    assert not theme.is_symlink()
    assert installation.plan("--uninstall")["changes"] == []
    for name in (".zshenv", ".zprofile", ".zshrc", ".config/git/config"):
        target = home / name
        assert not target.exists() or target.read_bytes() == b""


def test_config_upgrade_tracks_checkout_defaults_and_backs_up(installation: Installation) -> None:
    home = installation.home
    xdg = home.path / "personal config"
    home.env.update(XDG_CONFIG_HOME=str(xdg), AI_PROVIDER="claude", AI_ASK_RECENT="19")
    installation.apply()
    settings = xdg / "dotfiles/config.toml"
    original = (
        b'# personal\n[ai]\nprovider = "copilot"\nrecent = 0\n[ai.copilot]\n'
        b'model = "auto"\neffort = "low"\nflags = ["--example", "two words"]\n'
    )
    _ = settings.write_bytes(original)
    settings.chmod(0o640)
    schema = installation.source / ".config/dotfiles-defaults.json"
    updated = json.loads(schema.read_text())
    del updated["ai"]["copilot"]["effort"]
    updated["ai"]["copilot"]["new_option"] = 4
    _ = schema.write_text(json.dumps(updated))
    backups = installation.source / ".config-backups"
    preview = installation.plan()
    assert preview["changes"] == [{"path": str(settings), "operation": "reconcile"}]
    assert settings.read_bytes() == original and not backups.exists()
    result = installation.run("--apply", "--expected-plan", str(preview["planId"]))
    assert result.returncode == 0, result.stderr
    saved = Path(json.loads(result.stdout)["configBackup"])
    assert saved.parent == backups and saved.read_bytes() == original
    assert saved.stat().st_mode & 0o777 == 0o600
    assert git(home, installation.source, "check-ignore", "--", str(saved)).returncode == 0
    effective = tomllib.loads(settings.read_text())["ai"]
    assert (effective["provider"], effective["recent"]) == ("copilot", 0)
    assert effective["copilot"] == {
        "model": "auto",
        "flags": ["--example", "two words"],
        "new_option": 4,
    }
    assert effective["claude"] == {"flags": []}
    assert settings.stat().st_mode & 0o777 == 0o640
    with settings.open("ab") as stream:
        _ = stream.write(b"# keep this comment\n")
    assert installation.plan()["changes"] == []
    installation.apply()
    assert settings.read_bytes().endswith(b"# keep this comment\n")
    assert list(backups.iterdir()) == [saved]


def test_stale_or_malformed_config_stops_apply(installation: Installation) -> None:
    settings = installation.home.path / ".config/dotfiles/config.toml"
    plan_id = str(installation.plan()["planId"])
    settings.parent.mkdir(parents=True)
    _ = settings.write_text("[ai]\nrecent = 1\n")
    assert "stale-plan" in installation.run("--apply", "--expected-plan", plan_id).stderr
    _ = settings.write_text("[ai")
    assert installation.run().returncode != 0
    assert settings.read_text() == "[ai"
    assert not (installation.source / ".config-backups").exists()
    assert not (installation.home.path / ".zshenv").exists()


def test_upgrade_theme_only_block_keeps_personal_settings(installation: Installation) -> None:
    installation.apply()
    config = installation.home.path / ".config/ghostty/config.ghostty"
    previous = "# >>> amichne/dotfiles >>>\ntheme = Neon Arcade\n# <<< amichne/dotfiles <<<\n"
    personal = "cursor-opacity = 0.85\n"
    _ = config.write_text(previous + personal)
    installation.apply()
    shader = installation.source / ".config/ghostty/cursor-trail.glsl"
    assert config.read_text().count(f"custom-shader = {shader}\n") == 1
    assert installation.plan()["changes"] == []
    installation.apply("--uninstall")
    assert config.read_text() == personal


def test_layered_consumers_and_personal_files(installation: Installation) -> None:
    home = installation.home
    zdotdir = home.path / "shell files"
    config = home.path / "xdg config"
    home.env.update(ZDOTDIR=str(zdotdir), XDG_CONFIG_HOME=str(config))
    zdotdir.mkdir()
    (config / "git").mkdir(parents=True)
    hooks = {
        ".zshenv": b'print -r -- "env:$WORKTREE_ROOT" >> "$HOME/phases"\n',
        ".zprofile": (
            b'(( ${path[(Ie)$HOME/.local/bin]} )) && print -r -- login >> "$HOME/phases"\n'
        ),
        ".zshrc": b'print -r -- "interactive:${_SHELL_CONFIG_RESULT}" >> "$HOME/phases"\n',
    }
    for name, original in hooks.items():
        _ = (zdotdir / name).write_bytes(original)
        (zdotdir / name).chmod(0o640)
    config_file = config / "git/config"
    original_git = b"[alias]\n\troot = personal-root\n"
    _ = config_file.write_bytes(original_git)
    sibling = config / "git/ignore"
    ghostty = config / "ghostty/config.ghostty"
    ghostty.parent.mkdir()
    _ = ghostty.write_text("font-size = 17\n")
    _ = sibling.write_bytes(b"*.personal\n")
    functions = config / "zsh/functions"
    functions.mkdir(parents=True)
    _ = (functions / "rr").write_text("print -r -- personal-rr\n")
    log = prepare_integrations(home)
    installation.apply()
    assert not (home.path / ".zshrc").exists()
    assert not (home.path / ".config/starship.toml").exists()
    assert (config / "starship.toml").is_symlink()
    assert sibling.read_bytes() == b"*.personal\n"
    root = home.run("git", "config", "--get", "alias.root")
    assert root.returncode == 0 and root.stdout.strip() == "personal-root"
    main = home.run("git", "config", "--get", "alias.main")
    assert main.returncode == 0 and "git switch main" in main.stdout

    phases = home.path / "phases"
    env_phase = "env:" + str(home.path / ".worktrees")
    for flags, expected in (
        ("-c", [env_phase]),
        ("-lc", [env_phase, "login"]),
        ("-ic", [env_phase, "interactive:0"]),
        ("-lic", [env_phase, "login", "interactive:0"]),
    ):
        probe = 'autoload +X f && print -r -- "$functions_source[f]" && rr' if "i" in flags else ":"
        result = home.run("/bin/zsh", "-d", flags, probe)
        assert result.returncode == 0, result.stderr
        assert phases.read_text().splitlines() == expected
        if "i" in flags:
            assert result.stdout.splitlines() == [
                str(installation.source / ".config/zsh/functions/f"),
                "personal-rr",
            ]
        phases.unlink()
    assert log.read_text().splitlines().count("starship init zsh") == 2
    assert installation.plan()["changes"] == []
    edited = zdotdir / ".zshrc"
    with edited.open("ab") as stream:
        _ = stream.write(b"# later personal edit\n")
    installation.apply("--uninstall")
    assert edited.read_bytes() == hooks[".zshrc"] + b"# later personal edit\n"
    for name in (".zprofile", ".zshenv"):
        assert (zdotdir / name).read_bytes() == hooks[name]
    for name in hooks:
        assert (zdotdir / name).stat().st_mode & 0o777 == 0o640
    assert config_file.read_bytes() == original_git
    assert ghostty.read_text() == "font-size = 17\n"
    assert sibling.read_bytes() == b"*.personal\n"


@pytest.mark.parametrize("kind", ["occupied-starship", "symlink-parent", "bare-repo", "stale-hook"])
def test_apply_rechecks_before_changing_any_hook(installation: Installation, kind: str) -> None:
    home = installation.home.path
    plan_id = str(installation.plan()["planId"])
    config = home / ".config"
    outside = home.parent / "foreign"
    outside.mkdir()
    if kind == "occupied-starship":
        config.mkdir()
        _ = (config / "starship.toml").write_bytes(b"personal")
    elif kind == "symlink-parent":
        config.symlink_to(outside, target_is_directory=True)
    elif kind == "bare-repo":
        result = installation.home.run("git", "init", "--bare", str(home / ".dotfiles.git"))
        assert result.returncode == 0, result.stderr
    else:
        _ = (home / ".zshenv").write_text("# changed since preview\n")
    result = installation.run("--apply", "--expected-plan", plan_id)
    assert result.returncode != 0 and result.stderr
    assert not (home / ".zshrc").exists()
    assert not (home / ".zprofile").exists()
    assert not (config / "git/config").exists()
    assert list(outside.iterdir()) == []
    if kind == "occupied-starship":
        assert (config / "starship.toml").read_bytes() == b"personal"
    elif kind == "stale-hook":
        assert (home / ".zshenv").read_text() == "# changed since preview\n"
        assert not (config / "starship.toml").is_symlink()


def test_uninstall_preserves_replaced_link(installation: Installation) -> None:
    home = installation.home.path
    installation.apply()
    plan_id = str(installation.plan("--uninstall")["planId"])
    hook = (home / ".zshrc").read_bytes()
    starship = home / ".config/starship.toml"
    personal = home / "my-theme.toml"
    _ = personal.write_text("# personal theme\n")
    starship.unlink()
    starship.symlink_to(personal)
    result = installation.run("--uninstall", "--apply", "--expected-plan", plan_id)
    assert result.returncode != 0 and result.stderr
    assert (home / ".zshrc").read_bytes() == hook
    assert starship.readlink() == personal
    assert personal.read_text() == "# personal theme\n"


@pytest.mark.parametrize("kind", ["link", "hook"])
def test_matching_contents_do_not_establish_ownership(
    installation: Installation, kind: str
) -> None:
    home = installation.home.path
    installation.apply()
    hook = home / ".zshrc"
    copied = hook.read_bytes()
    starship = home / ".config/starship.toml"
    target = starship.readlink()
    installation.apply("--uninstall")
    if kind == "hook":
        _ = hook.write_bytes(copied)
    else:
        starship.symlink_to(target)
    plan = installation.run()
    assert plan.returncode != 0 and plan.stderr
    assert installation.plan("--uninstall")["changes"] == []
    installation.apply("--uninstall")
    if kind == "hook":
        assert hook.read_bytes() == copied
    else:
        assert starship.readlink() == target
