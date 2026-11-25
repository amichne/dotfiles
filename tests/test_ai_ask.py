from __future__ import annotations

import json
import subprocess
import sys

import pytest

from .conftest import Home


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        (
            "codex",
            [
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--color",
                "never",
                "-",
            ],
        ),
        (
            "copilot",
            [
                "--silent",
                "--stream",
                "off",
                "--available-tools",
                "--disable-builtin-mcps",
                "--no-custom-instructions",
            ],
        ),
        (
            "claude",
            [
                "--print",
                "--output-format",
                "text",
                "--no-session-persistence",
                "--strict-mcp-config",
                "--tools",
                "",
            ],
        ),
    ],
)
def test_prompt_from_another_cli(home: Home, provider: str, expected: list[str]) -> None:
    binary = home.tools / provider
    _ = binary.write_text(
        f"#!{sys.executable}\nimport json, sys\n"
        "print(json.dumps([sys.argv[1:], sys.stdin.read()]))\n"
    )
    binary.chmod(0o755)
    env = home.env.copy()
    args = [str(home.path / ".local/bin/ai-ask")]
    if provider == "copilot":
        env["AI_PROVIDER"] = provider
    if provider == "claude":
        env["AI_PROVIDER"] = "copilot"
        args.extend(["--provider", provider])
    prompt = "--literal\n$(touch unwanted)"
    result = subprocess.run(
        args, input=prompt, text=True, capture_output=True, env=env, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [expected, prompt]


def test_provider_errors_never_become_answers(home: Home) -> None:
    cmd = str(home.path / ".local/bin/ai-ask")
    home.env["AI_PROVIDER"] = "unknown"
    assert home.run(cmd, "text").returncode == 2
    home.env["AI_PROVIDER"] = "codex"
    assert home.run(cmd, "  ").returncode == 2
    assert home.run(cmd, "text").returncode == 127
    binary = home.tools / "codex"
    _ = binary.write_text("#!/bin/sh\necho partial\nexit 17\n")
    binary.chmod(0o755)
    failed = home.run(cmd, "text")
    assert (failed.returncode, failed.stdout) == (17, "")
    _ = binary.write_text("#!/bin/sh\nexit 0\n")
    empty = home.run(cmd, "text")
    assert empty.returncode == 1 and not empty.stdout
