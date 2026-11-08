from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".local/bin/setup-tools"
CONFIG = """[tools]
node = "26.0.0"
uv = "0.12.9"
[vars]
setup_brew_formulae = "git neovim"
setup_brew_casks = "example-app"
"""


@pytest.fixture
def setup(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    config = tmp_path / "config with spaces.toml"
    _ = config.write_text(CONFIG)
    tools = tmp_path / "tools"
    tools.mkdir()
    for provider in ("brew", "mise"):
        tool = tools / provider
        _ = tool.write_text(
            f"#!{sys.executable}\n"
            "import json, os, signal, sys, time\n"
            "from pathlib import Path\n"
            "name = Path(sys.argv[0]).name\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['CALLS'], 'a') as stream:\n"
            "    stream.write(json.dumps([name, *args]) + '\\n')\n"
            "if os.environ.get('CHECK_ENV'):\n"
            "    assert os.environ['HOMEBREW_NO_AUTO_UPDATE'] == '1'\n"
            "    assert os.environ['HOMEBREW_NO_INSTALL_UPGRADE'] == '1'\n"
            "    assert os.environ['HOMEBREW_NO_INSTALL_CLEANUP'] == '1'\n"
            "    assert os.environ['MISE_AUTO_INSTALL'] == 'false'\n"
            "    assert os.environ['MISE_TASK_RUN_AUTO_INSTALL'] == 'false'\n"
            "    assert os.environ['MISE_CONFIG_FILE'] == os.environ['MISE_GLOBAL_CONFIG_FILE']\n"
            "if name == 'brew' and args[0] == 'list':\n"
            "    sys.exit(0 if args[-1] == 'git' else 1)\n"
            "if os.environ.get('CANCEL') == name:\n"
            "    os.kill(os.getpid(), signal.SIGTERM)\n"
            "if os.environ.get('SLOW') == name:\n"
            "    time.sleep(30)\n"
            "if args[-1] == 'node@26.0.0':\n"
            "    print('x' * int(os.environ.get('NOISY', '0')), file=sys.stderr)\n"
            "    print('fixture: download unavailable', file=sys.stderr)\n"
            "    sys.exit(7)\n"
        )
        tool.chmod(0o755)
    env = {
        "PATH": str(tools),
        "HOME": str(tmp_path),
        "CALLS": str(tmp_path / "calls.jsonl"),
        "LANG": "C.UTF-8",
    }
    return config, env


def invoke(setup: tuple[Path, dict[str, str]], *args: str) -> subprocess.CompletedProcess[str]:
    config, env = setup
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(config), "--json", *args],
        cwd=config.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def calls(env: dict[str, str]) -> list[list[str]]:
    path = Path(env["CALLS"])
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_plan_is_offline_and_never_invokes_a_provider(setup: tuple[Path, dict[str, str]]) -> None:
    result = invoke(setup)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "planned"
    assert [item["target"] for item in report["items"]] == [
        "brew:git",
        "brew:neovim",
        "cask:example-app",
        "mise:node@26.0.0",
        "mise:uv@0.12.9",
    ]
    assert report["items"][1]["command"] == ["brew", "install", "--formula", "neovim"]
    assert calls(setup[1]) == []


@pytest.mark.parametrize("strict, expected", [(False, 0), (True, 1)])
def test_failures_are_reported_and_do_not_block_later_installs(
    setup: tuple[Path, dict[str, str]], strict: bool, expected: int
) -> None:
    setup[1]["CHECK_ENV"] = "1"
    result = invoke(setup, "--apply", *(["--strict"] if strict else []))
    assert result.returncode == expected, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "partial"
    assert [item["outcome"] for item in report["items"]] == [
        "already-installed",
        "ready",
        "ready",
        "failed",
        "ready",
    ]
    assert report["items"][3]["code"] == 7
    assert "download unavailable" in result.stderr
    assert calls(setup[1]) == [
        ["brew", "list", "--formula", "--versions", "git"],
        ["brew", "list", "--formula", "--versions", "neovim"],
        ["brew", "install", "--formula", "neovim"],
        ["brew", "list", "--cask", "--versions", "example-app"],
        ["brew", "install", "--cask", "example-app"],
        ["mise", "install", "node@26.0.0"],
        ["mise", "install", "uv@0.12.9"],
    ]


def test_missing_brew_does_not_block_mise(setup: tuple[Path, dict[str, str]]) -> None:
    _, env = setup
    (Path(env["PATH"]) / "brew").unlink()
    result = invoke(setup, "--apply")
    report = json.loads(result.stdout)
    assert report["status"] == "partial"
    assert [item["outcome"] for item in report["items"]][:3] == ["missing-provider"] * 3
    assert calls(env)[-1] == ["mise", "install", "uv@0.12.9"]


def test_provider_selection(setup: tuple[Path, dict[str, str]]) -> None:
    result = invoke(setup, "--apply", "--provider", "brew", "--strict")
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "complete"
    assert all(call[0] == "brew" for call in calls(setup[1]))


@pytest.mark.parametrize(
    "config",
    [
        CONFIG.replace('"26.0.0"', '"latest"'),
        CONFIG.replace('"26.0.0"', '"26"'),
        CONFIG.replace('"26.0.0"', '["26.0.0"]'),
        CONFIG.replace('"git neovim"', '"--force neovim"'),
        CONFIG.replace('"git neovim"', '"git git"'),
        CONFIG.replace('"git neovim"', '"git;echo bad"'),
        '[tools]\nnode = "26.0.0"\n',
        "[tools\n",
        '[tools]\n[vars]\nsetup_brew_formulae = ""\nsetup_brew_casks = ""\n',
    ],
)
def test_invalid_or_empty_inventory_fails_before_any_install(
    setup: tuple[Path, dict[str, str]], config: str
) -> None:
    _ = setup[0].write_text(config)
    result = invoke(setup, "--apply")
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "invalid-config"
    assert calls(setup[1]) == []


def test_missing_config_is_an_error_not_empty_success(setup: tuple[Path, dict[str, str]]) -> None:
    setup[0].unlink()
    result = invoke(setup, "--apply")
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "unreadable-config"
    assert calls(setup[1]) == []


def test_cancellation_is_not_safe_to_ignore(setup: tuple[Path, dict[str, str]]) -> None:
    setup[1]["CANCEL"] = "mise"
    result = invoke(setup, "--apply")
    assert result.returncode == 128 + signal.SIGTERM
    assert json.loads(result.stdout)["status"] == "interrupted"
    assert calls(setup[1])[-1] == ["mise", "install", "node@26.0.0"]


@pytest.mark.parametrize("number", [signal.SIGINT, signal.SIGTERM])
def test_interrupting_the_runner_stops_before_the_next_item(
    setup: tuple[Path, dict[str, str]], number: int
) -> None:
    config, env = setup
    env["SLOW"] = "mise"
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--config", str(config), "--json", "--apply"],
        cwd=config.parent,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5
        while ["mise", "install", "node@26.0.0"] not in calls(env):
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.01)
        process.send_signal(number)
        output, errors = process.communicate(timeout=5)
        assert process.returncode == 128 + number, errors
        assert json.loads(output)["status"] == "interrupted"
        assert calls(env)[-1] == ["mise", "install", "node@26.0.0"]
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            _ = process.communicate(timeout=5)


def test_timeout_is_bounded_and_later_items_still_run(setup: tuple[Path, dict[str, str]]) -> None:
    setup[1]["SLOW"] = "mise"
    result = invoke(setup, "--apply", "--timeout", "0.1")
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["status"] == "partial"
    assert [item["outcome"] for item in report["items"]][-2:] == ["timed-out", "timed-out"]
    assert calls(setup[1])[-1] == ["mise", "install", "uv@0.12.9"]


@pytest.mark.parametrize("argument", ["--aply", "--apply=true", "--timeout=0", "--timeout=nan"])
def test_bad_arguments_are_rejected_without_effects(
    setup: tuple[Path, dict[str, str]], argument: str
) -> None:
    result = invoke(setup, argument)
    assert result.returncode == 2
    assert calls(setup[1]) == []


def test_noisy_failures_do_not_flood_the_report(setup: tuple[Path, dict[str, str]]) -> None:
    setup[1]["NOISY"] = "20000"
    result = invoke(setup, "--apply")
    assert len(result.stderr) < 3000
    assert "fixture: download unavailable" in result.stderr
    assert json.loads(result.stdout)["status"] == "partial"


def test_nonexecutable_provider_is_reported_and_other_provider_continues(
    setup: tuple[Path, dict[str, str]],
) -> None:
    (Path(setup[1]["PATH"]) / "brew").chmod(0o644)
    result = invoke(setup, "--apply")
    report = json.loads(result.stdout)
    assert report["items"][0]["outcome"] == "cannot-start"
    assert calls(setup[1])[-1] == ["mise", "install", "uv@0.12.9"]


def test_whole_inventory_is_validated_even_when_selecting_one_provider(
    setup: tuple[Path, dict[str, str]],
) -> None:
    _ = setup[0].write_text(CONFIG.replace('"git neovim"', '"--force"'))
    result = invoke(setup, "--apply", "--provider", "mise")
    assert result.returncode == 2
    assert calls(setup[1]) == []


def test_public_config_and_task_contract() -> None:
    import tomllib

    config = tomllib.loads((ROOT / ".config/mise/config.toml").read_text())
    assert config["settings"]["task"]["run_auto_install"] is False
    assert {"setup", "setup:plan", "setup:strict"} <= config["tasks"].keys()
    assert "--apply" not in config["tasks"]["setup:plan"]["run"]
    assert "--apply" in config["tasks"]["setup"]["run"]
    assert "--strict" in config["tasks"]["setup:strict"]["run"]
    assert os.access(SCRIPT, os.X_OK)
