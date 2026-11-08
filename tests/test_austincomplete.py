from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import Home
from .test_home_source import prepare_integrations

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / ".local/bin/austincomplete"


@pytest.fixture
def environment(tmp_path: Path) -> dict[str, str]:
    return {
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config with spaces"),
        "XDG_CACHE_HOME": str(tmp_path / "cache with spaces"),
        "PATH": "/usr/bin:/bin",
    }


def invoke(env: dict[str, str], *args: str, content: str = "") -> subprocess.CompletedProcess[str]:
    assert CLI.is_file(), "austincomplete executable is missing"
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        input=content,
        text=True,
        capture_output=True,
        env=env,
        cwd=env["HOME"],
        timeout=10,
        check=False,
    )


def cached(env: dict[str, str], name: str = "demo") -> Path:
    return Path(env["XDG_CACHE_HOME"]) / "austincomplete/zsh" / ("_" + name)


def recipe(env: dict[str, str], name: str = "demo") -> Path:
    return Path(env["XDG_CONFIG_HOME"]) / "austincomplete/recipes" / (name + ".json")


def generator(tmp_path: Path) -> Path:
    path = tmp_path / "generator with spaces.py"
    _ = path.write_text(
        "import pathlib, sys\n"
        "value = pathlib.Path(sys.argv[1]).read_text()\n"
        "print('#compdef demo\\n_arguments ' + repr(value))\n"
    )
    return path


def test_register_infers_caller_and_update_replays_literal_arguments(
    environment: dict[str, str], tmp_path: Path
) -> None:
    value = tmp_path / "value ; $(not-evaluated)"
    _ = value.write_text("--old")
    script = generator(tmp_path)
    # Explicit name permits generators whose executable differs from the caller.
    args = (sys.executable, str(script), str(value))
    result = invoke(environment, "add", "demo", "--", *args)
    assert result.returncode == 0, result.stderr
    assert "--old" in cached(environment).read_text()
    assert json.loads(recipe(environment).read_text()) == {
        "version": 1,
        "kind": "generator",
        "argv": list(args),
    }
    _ = value.write_text("--new")
    result = invoke(environment, "update", "demo")
    assert result.returncode == 0, result.stderr
    assert "--new" in cached(environment).read_text()


def test_infer_name_from_base_executable(environment: dict[str, str], tmp_path: Path) -> None:
    executable = tmp_path / "demo"
    _ = executable.write_text("#!/bin/sh\nprintf '#compdef demo\\n_arguments --version\\n'\n")
    executable.chmod(0o755)
    result = invoke(environment, "add", "--", str(executable))
    assert result.returncode == 0, result.stderr
    assert recipe(environment).is_file()


def test_pipe_is_static_unless_generator_is_explicit(environment: dict[str, str]) -> None:
    result = invoke(environment, "add", "demo", content="#compdef demo\n_arguments --help\n")
    assert result.returncode == 0, result.stderr
    original = cached(environment).read_bytes()
    result = invoke(environment, "update", "demo")
    assert result.returncode != 0
    assert "static-completion" in result.stderr
    assert cached(environment).read_bytes() == original


def test_pipe_can_save_recipe_without_running_it(environment: dict[str, str]) -> None:
    result = invoke(
        environment,
        "add",
        "demo",
        "--stdin",
        "--",
        "missing-demo",
        "completion",
        "zsh",
        content="#compdef demo\n_arguments --help\n",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(recipe(environment).read_text())["argv"] == [
        "missing-demo",
        "completion",
        "zsh",
    ]
    result = invoke(environment, "update", "demo")
    assert result.returncode != 0
    assert "missing-command" in result.stderr


@pytest.mark.parametrize(
    "content", ["", "echo wrong-shell\n", "#compdef other\n:", "#compdef demo\nif"]
)
def test_invalid_output_preserves_previous_completion(
    environment: dict[str, str], content: str
) -> None:
    result = invoke(environment, "add", "demo", content="#compdef demo\n_arguments --good\n")
    assert result.returncode == 0, result.stderr
    original = cached(environment).read_bytes(), recipe(environment).read_bytes()
    result = invoke(environment, "add", "demo", content=content)
    assert result.returncode != 0
    assert (cached(environment).read_bytes(), recipe(environment).read_bytes()) == original


def test_failed_generator_never_replaces_previous_files(environment: dict[str, str]) -> None:
    result = invoke(environment, "add", "demo", content="#compdef demo\n_arguments --good\n")
    assert result.returncode == 0, result.stderr
    original = cached(environment).read_bytes(), recipe(environment).read_bytes()
    result = invoke(environment, "add", "demo", "--", "/bin/sh", "-c", "printf bad; exit 7")
    assert result.returncode == 7
    assert "generator-failed" in result.stderr
    assert (cached(environment).read_bytes(), recipe(environment).read_bytes()) == original


@pytest.mark.parametrize("name", ["../escape", "-demo", "a/b", "a\nb"])
def test_invalid_name_has_no_effects(environment: dict[str, str], name: str) -> None:
    result = invoke(
        environment, "add", name, "--", "/usr/bin/touch", str(Path(environment["HOME"]) / "ran")
    )
    assert result.returncode != 0
    assert not (Path(environment["HOME"]) / "ran").exists()
    assert not Path(environment["XDG_CONFIG_HOME"]).exists()


def test_update_all_continues_after_failure_and_skips_static(
    environment: dict[str, str], tmp_path: Path
) -> None:
    for name, argv in [("bad", ["missing-tool"]), ("demo", ["/bin/echo", "#compdef demo\n:"])]:
        result = invoke(
            environment, "add", name, "--stdin", "--", *argv, content=f"#compdef {name}\n:\n"
        )
        assert result.returncode == 0, result.stderr
    assert invoke(environment, "add", "static", content="#compdef static\n:\n").returncode == 0
    result = invoke(environment, "update", "--all")
    assert result.returncode != 0
    assert "missing-command" in result.stderr
    assert "updated demo" in result.stdout
    assert "skipped-static static" in result.stdout
    assert cached(environment).read_text() == "#compdef demo\n:\n"


def test_rejects_corrupt_registry_before_any_generator(environment: dict[str, str]) -> None:
    directory = recipe(environment).parent
    directory.mkdir(parents=True)
    _ = recipe(environment).write_text('{"version": 1, "kind": "generator", "argv": []}')
    result = invoke(environment, "update", "--all")
    assert result.returncode != 0
    assert "invalid-recipe" in result.stderr
    assert not cached(environment).exists()


@pytest.mark.parametrize(
    "content",
    [
        '{"version": 1, "kind": "static", "kind": "generator", "argv": ["missing"]}',
        '{"version": true, "kind": "static"}',
        '{"version": 2, "kind": "static"}',
        '{"version": 1, "kind": "static", "argv": ["missing"]}',
        '{"version": 1, "kind": "generator", "argv": [42]}',
    ],
)
def test_recipe_schema_is_closed(environment: dict[str, str], content: str) -> None:
    recipe(environment).parent.mkdir(parents=True)
    _ = recipe(environment).write_text(content)
    result = invoke(environment, "list", "--json")
    assert result.returncode == 2
    assert "invalid-recipe" in result.stderr


def test_fresh_shell_prefers_saved_completions_without_generating(home: Home) -> None:
    log = prepare_integrations(home)
    for name in ("atuin", "mise"):
        target = cached(home.env, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(f"#compdef {name}\n_arguments --saved\n")
    result = home.run(
        "/bin/zsh",
        "-d",
        "-i",
        "-c",
        'print -rl -- "$_comps[atuin]" "$_comps[mise]" "$_comps[austincomplete]"; '
        'return "$_SHELL_CONFIG_RESULT"',
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["_atuin", "_mise", "_austincomplete"]
    assert "atuin gen-completions --shell zsh" not in log.read_text()
    assert "mise completion zsh" not in log.read_text()


def test_rejects_symlink_destination(environment: dict[str, str], tmp_path: Path) -> None:
    directory = cached(environment).parent
    directory.mkdir(parents=True)
    victim = tmp_path / "victim"
    _ = victim.write_text("untouched")
    cached(environment).symlink_to(victim)
    result = invoke(environment, "add", "demo", content="#compdef demo\n:\n")
    assert result.returncode != 0
    assert "unsafe-path" in result.stderr
    assert victim.read_text() == "untouched"


def test_size_limit(environment: dict[str, str]) -> None:
    result = invoke(
        environment, "add", "demo", content="#compdef demo\n#" + "x" * (4 * 1024 * 1024)
    )
    assert result.returncode != 0
    assert "completion-too-large" in result.stderr
    assert not cached(environment).exists()


def test_help_and_empty_list(environment: dict[str, str]) -> None:
    assert invoke(environment, "--help").returncode == 0
    result = invoke(environment, "list")
    assert result.returncode == 0, result.stderr
    assert "0 completions" in result.stdout
    result = invoke(environment, "update")
    assert result.returncode == 2
    result = invoke(environment, "update", "--all", "demo")
    assert result.returncode == 2
    assert not Path(environment["XDG_CONFIG_HOME"]).exists()


def test_shell_wrapper_refreshes_completion_even_at_pipeline_end(
    environment: dict[str, str], tmp_path: Path
) -> None:
    assert CLI.is_file(), "austincomplete executable is missing"
    # Use an existing interpreter, not uv installation or host shell startup.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    launcher = bin_dir / "austincomplete"
    _ = launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{CLI}" "$@"\n')
    launcher.chmod(0o755)
    environment["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    wrapper = ROOT / ".config/zsh/functions/austincomplete"
    result = subprocess.run(
        [
            "/bin/zsh",
            "-dfc",
            f'''
        fpath=("{wrapper.parent}" $fpath)
        autoload -Uz austincomplete compinit
        compinit -i -D
        print -r -- '#compdef demo\n_arguments --old' | austincomplete add demo
        [[ $_comps[demo] == _demo ]] || exit 21
        autoload +X _demo
        print -r -- '#compdef demo\n_arguments --new' | austincomplete add demo
        [[ $functions[_demo] != *--old* ]] || exit 22
        [[ $fpath[1] == "$XDG_CACHE_HOME/austincomplete/zsh" ]] || exit 23
        print -r -- "$_comps[demo]"
        ''',
        ],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "_demo" in result.stdout
    assert os.access(CLI, os.X_OK)
