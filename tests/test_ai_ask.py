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


def test_terminal_alias_in_argument_and_pipeline_positions(home: Home) -> None:
    provider = home.tools / "codex"
    _ = provider.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "task, data = sys.stdin.read().split('\\n', 1)\n"
        "context = json.loads(data)\n"
        "assert context['working_directory'] == os.getcwd()\n"
        "with Path('requests').open('a') as log: print(data, file=log)\n"
        "if context['instruction'] == 'filter': print('interface Result')\n"
        "elif context['instruction'] == 'render': print('rendered ' + context['stdin'].strip())\n"
        "elif 'staged_diff' in context: print('add result interface')\n"
        "elif 'refuse' in context['command_line']: print('AI_ASK_NO_ARGUMENT')\n"
        "else: print('one argument with $(touch oops) and *')\n"
    )
    provider.chmod(0o755)
    line = 'printf "raw diff" | $A "filter" | $A "render"'
    shell = subprocess.run(
        ["zsh", "-dfi"],
        input="\n".join(
            (
                'source "$HOME/.zshrc"',
                "mkdir project && cd project",
                line,
                """printf 'bare input' | $A""",
                """$A 'describe this directory' </dev/null""",
                """printf '<%s>\\n' $A""",
                """print -r -- 'literal $A'""",
                "git init -q",
                "print 'interface Result' > Test.kt && git add Test.kt",
                "git commit -m $A",
                "git commit -m $A",
                "touch refuse $A",
                "exit 0\n",
            )
        ),
        env={
            **home.env,
            "GIT_AUTHOR_NAME": "User",
            "GIT_AUTHOR_EMAIL": "user@example.org",
            "GIT_COMMITTER_NAME": "User",
            "GIT_COMMITTER_EMAIL": "user@example.org",
        },
        cwd=home.path,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert shell.returncode == 0, shell.stderr
    assert "rendered interface Result" in shell.stdout
    assert "<one argument with $(touch oops) and *>" in shell.stdout
    assert "literal $A" in shell.stdout
    project = home.path / "project"
    calls = [json.loads(row) for row in (project / "requests").read_text().splitlines()]
    assert [(c["instruction"], c["stdin"]) for c in calls[:2]] == [
        ("filter", "raw diff"),
        ("render", "interface Result\n"),
    ]
    assert all(c["command_line"] == line for c in calls[:2])
    assert calls[2]["instruction"] is None and calls[2]["stdin"] == "bare input"
    assert calls[3]["instruction"] == "describe this directory"
    assert calls[4]["stdin"] is None
    assert "+interface Result" in calls[5]["staged_diff"]
    subject = home.run("git", "-C", str(project), "log", "-1", "--format=%s")
    assert subject.stdout.strip() == "add result interface"
    assert "no staged changes" in shell.stderr
    assert len(calls) == 7
    assert not (project / "oops").exists() and not (project / "refuse").exists()


def test_terminal_readback_uses_completed_session_entries_and_their_output(home: Home) -> None:
    atuin = home.tools / "atuin"
    _ = atuin.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "if sys.argv[1] == 'search':\n"
        "    assert sys.argv[2:4] == ['--filter-mode', 'session']\n"
        "    sys.stdout.write('first\\t0\\tbuild\\0second\\t1\\ttest\\0now\\t-1\\task\\0')\n"
        "else:\n"
        "    for raw in sys.stdin:\n"
        "        m = json.loads(raw)\n"
        "        if 'id' not in m: continue\n"
        "        if m['method'] == 'initialize': result = {'capabilities': {'tools': {}}}\n"
        "        else:\n"
        "            args = m['params']['arguments']\n"
        "            assert m['params']['name'] == 'atuin_output'\n"
        "            assert args == {'history_id': 'second', 'ranges': [[-40, -1]]}\n"
        "            result = {'content': [{'type': 'text', 'text': 'unresolved reference'}]}\n"
        "        print(json.dumps({'id': m['id'], 'result': result}), flush=True)\n"
    )
    atuin.chmod(0o755)
    provider = home.tools / "codex"
    _ = provider.write_text("#!/bin/sh\ncat\n")
    provider.chmod(0o755)
    home.env.update(ATUIN_SESSION="fixture", AI_ASK_RECENT="1")
    cmd = str(home.path / ".local/bin/ai-ask")
    result = home.run(cmd, "--terminal", "argument")
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout.split("\n", 1)[1])
    assert context["recent_activity"] == [
        {
            "history_id": "second",
            "exit_code": 1,
            "command": "test",
            "output_tail": "unresolved reference",
        }
    ]
    atuin.unlink()
    missing = home.run(cmd, "--terminal", "argument")
    assert json.loads(missing.stdout.split("\n", 1)[1])["recent_activity"] == []
