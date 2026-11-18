"""Read-only probes for the installed Dotfiles consumers."""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeGuard


@dataclass(frozen=True, slots=True)
class Result:
    name: str
    outcome: Literal["passed", "failed", "unavailable", "timed-out", "invalid-data"]
    detail: str
    repair: str


@dataclass(frozen=True, slots=True)
class Output:
    text: str


def record(value: object) -> TypeGuard[dict[str, object]]:
    # JSON object keys are strings by the JSON decoder contract.
    return isinstance(value, dict)


def sequence(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def probe(
    name: str, args: list[str], home: Path, env: dict[str, str], repair: str
) -> Output | Result:
    # Temporary output stays outside HOME. Bound reads and process duration.
    with tempfile.TemporaryFile() as stream:
        try:
            result = subprocess.run(
                args,
                cwd=home,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except FileNotFoundError:
            return Result(name, "unavailable", "Executable is absent", repair)
        except PermissionError:
            return Result(name, "unavailable", "Executable cannot start", repair)
        except subprocess.TimeoutExpired:
            return Result(name, "timed-out", "Probe exceeded 10 seconds", repair)
        if result.returncode < 0:
            raise KeyboardInterrupt
        if result.returncode:
            return Result(name, "failed", f"Probe returned {result.returncode}", repair)
        _ = stream.seek(0)
        content = stream.read(65537)
        if len(content) > 65536:
            return Result(name, "invalid-data", "Probe output exceeds 64 KiB", repair)
        try:
            return Output(content.decode("utf-8"))
        except UnicodeError:
            return Result(name, "invalid-data", "Probe output is not UTF-8", repair)


def read_json(output: Output) -> object:
    return json.loads(output.text)


def tools(home: Path, env: dict[str, str]) -> list[Result]:
    repair = "setup-tools --apply --strict"
    config = Path(
        env.get(
            "MISE_GLOBAL_CONFIG_FILE",
            str(Path(env.get("XDG_CONFIG_HOME", str(home / ".config"))) / "mise/config.toml"),
        )
    )
    selected = {**env, "MISE_CONFIG_FILE": str(config), "MISE_GLOBAL_CONFIG_FILE": str(config)}
    output = probe(
        "inventory",
        [sys.executable, str(home / ".local/bin/setup-tools"), "--config", str(config), "--json"],
        home,
        selected,
        "setup-tools --json",
    )
    if isinstance(output, Result):
        return [output]
    raw = read_json(output)
    rows = raw.get("items") if record(raw) else None
    if not record(raw) or raw.get("status") != "planned" or not sequence(rows) or not rows:
        return [Result("inventory", "invalid-data", "Inventory has no items", "setup-tools --json")]
    results: list[Result] = []
    for row in rows:
        target = row.get("target") if record(row) else None
        if not isinstance(target, str) or ":" not in target:
            return [
                Result("inventory", "invalid-data", "Invalid inventory item", "setup-tools --json")
            ]
        provider, spec = target.split(":", 1)
        if provider == "mise":
            expected = probe(target, ["mise", "where", spec], home, selected, repair)
            if isinstance(expected, Result):
                results.append(expected)
                continue
            active = probe(target, ["mise", "where", spec.split("@", 1)[0]], home, selected, repair)
            if isinstance(active, Result):
                results.append(active)
            elif (
                not Path(expected.text.strip()).is_absolute()
                or active.text.strip() != expected.text.strip()
            ):
                results.append(
                    Result(
                        target,
                        "failed",
                        "Selected installation differs from the pin",
                        "mise current",
                    )
                )
            else:
                results.append(Result(target, "passed", expected.text.strip(), ""))
        elif provider in {"brew", "cask"}:
            output = probe(
                target,
                [
                    "brew",
                    "list",
                    "--cask" if provider == "cask" else "--formula",
                    "--versions",
                    spec,
                ],
                home,
                selected,
                repair,
            )
            results.append(
                output
                if isinstance(output, Result)
                else Result(target, "passed", "Package is installed", "")
            )
        else:
            results.append(
                Result("inventory", "invalid-data", "Unknown provider", "setup-tools --json")
            )
    return results


def completions(home: Path, env: dict[str, str]) -> list[Result]:
    repair = "austincomplete list --json"
    output = probe(
        "completions",
        [sys.executable, str(home / ".local/bin/austincomplete"), "list", "--json"],
        home,
        env,
        repair,
    )
    if isinstance(output, Result):
        return [output]
    rows = read_json(output)
    if not sequence(rows):
        return [Result("completions", "invalid-data", "Invalid recipe list", repair)]
    results: list[Result] = []
    cache = Path(env.get("XDG_CACHE_HOME", str(home / ".cache"))) / "austincomplete/zsh"
    for row in rows:
        if not record(row):
            return [Result("completions", "invalid-data", "Invalid completion record", repair)]
        name = row.get("command") if record(row) else None
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", name) is None:
            return [Result("completions", "invalid-data", "Invalid completion name", repair)]
        path = cache / f"_{name}"
        fix = (
            shlex.join(["austincomplete", "update", name])
            if row.get("kind") == "generator"
            else f"Regenerate the static completion for {name}"
        )
        if not path.is_file():
            results.append(Result(f"completion:{name}", "failed", "Cache file is absent", fix))
        else:
            result = probe(f"completion:{name}", ["zsh", "-n", str(path)], home, env, fix)
            results.append(
                result
                if isinstance(result, Result)
                else Result(f"completion:{name}", "passed", "Cache syntax passed", "")
            )
    return results or [Result("completions", "passed", "No registered completions", "")]


def run(home: Path, env: dict[str, str], identity: Result, structured: bool) -> int:
    env = {
        **env,
        "MISE_OFFLINE": "1",
        "MISE_AUTO_INSTALL": "false",
        "MISE_TASK_RUN_AUTO_INSTALL": "false",
        "HOMEBREW_NO_AUTO_UPDATE": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    results = [identity]
    # Identity rejection stops dependent inspection of the installation.
    if identity.outcome == "passed":
        try:
            results.extend(tools(home, env))
            results.extend(completions(home, env))
            results.extend(editor(home, env))
            for executable in ("mise", "starship", "atuin", "zoxide", "fzf"):
                resolved = shutil.which(executable, path=env.get("PATH", ""))
                results.append(
                    Result(
                        f"shell:command:{executable}",
                        "passed" if resolved else "unavailable",
                        resolved or "Executable is absent",
                        "" if resolved else "mise run setup:strict",
                    )
                )
            for path in [
                home / ".zshenv",
                home / ".zprofile",
                home / ".zshrc",
                *sorted((home / ".config/zsh/functions").glob("*")),
            ]:
                if path.is_file():
                    name = f"shell:{path.relative_to(home)}"
                    output = probe(name, ["zsh", "-n", str(path)], home, env, f"Examine {path}")
                    results.append(
                        output
                        if isinstance(output, Result)
                        else Result(name, "passed", "Syntax passed", "")
                    )
            for name in (".zshenv", ".zprofile", ".zshrc"):
                if not (home / name).is_file():
                    results.append(
                        Result(
                            f"shell:{name}",
                            "failed",
                            "Startup file is absent",
                            "dotfiles setup plan",
                        )
                    )
            # Pi uses its native HOME path, independently of XDG configuration.
            config = home / ".pi/agent/pi-lsp.json"
            data: object = json.loads(config.read_text())
            servers = data.get("servers") if record(data) else None
            if not record(servers):
                results.append(
                    Result("pi", "invalid-data", "Expected servers object", f"Examine {config}")
                )
            else:
                for name, server in servers.items():
                    command = server.get("command") if record(server) else None
                    if not sequence(command) or not command or not isinstance(command[0], str):
                        results.append(
                            Result(
                                f"pi:{name}",
                                "invalid-data",
                                "Expected executable",
                                f"Examine {config}",
                            )
                        )
                    else:
                        executable = shutil.which(command[0], path=env.get("PATH", ""))
                        results.append(
                            Result(
                                f"pi:{name}",
                                "passed" if executable else "unavailable",
                                executable or f"Missing {command[0]}",
                                "" if executable else "mise run setup:strict",
                            )
                        )
        except (OSError, ValueError) as error:
            results.append(
                Result(
                    "configuration",
                    "invalid-data",
                    type(error).__name__,
                    "Examine the configuration files",
                )
            )
    status = "healthy" if all(row.outcome == "passed" for row in results) else "unhealthy"
    if structured:
        print(
            json.dumps(
                {
                    "status": status,
                    "items": [
                        {
                            "name": row.name,
                            "outcome": row.outcome,
                            "detail": row.detail,
                            "repair": row.repair,
                        }
                        for row in results
                    ],
                }
            )
        )
    else:
        print(f"dotfiles doctor: {status}")
        for row in results:
            print(f"{row.outcome}: {row.name}: {row.detail}")
            if row.repair:
                print(f"  Repair: {row.repair}")
    return 0 if status == "healthy" else 1


def editor(home: Path, env: dict[str, str]) -> list[Result]:
    repair = "nvim '+checkhealth editor'"
    lua = "local m=dofile(vim.env.DOTFILES_DOCTOR_LSP); io.write(vim.json.encode({version=vim.fn.has('nvim-0.12'),servers=m.status()}))"
    output = probe(
        "editor",
        [
            "nvim",
            "--headless",
            "--noplugin",
            "-u",
            "NONE",
            "-i",
            "NONE",
            "-n",
            "-c",
            f"lua {lua}",
            "-c",
            "qa!",
        ],
        home,
        {
            **env,
            "DOTFILES_DOCTOR_LSP": str(home / ".config/nvim/lua/editor/lsp.lua"),
            "NVIM_LOG_FILE": "/dev/null",
        },
        repair,
    )
    if isinstance(output, Result):
        return [output]
    raw = read_json(output)
    if not record(raw) or not sequence(raw.get("servers")):
        return [Result("editor", "invalid-data", "Invalid editor status", repair)]
    results = [
        Result(
            "editor:version",
            "passed" if raw.get("version") == 1 else "failed",
            "Neovim 0.12 or later",
            repair,
        )
    ]
    rows = raw["servers"]
    if not sequence(rows) or not rows:
        return [Result("editor", "invalid-data", "Invalid server list", repair)]
    for row in rows:
        if (
            not record(row)
            or not isinstance(row.get("server"), str)
            or row.get("outcome") not in ("ENABLED", "MISSING_EXECUTABLE")
        ):
            return [Result("editor", "invalid-data", "Invalid server status", repair)]
        results.append(
            Result(
                f"editor:{row['server']}",
                "passed" if row["outcome"] == "ENABLED" else "unavailable",
                str(row.get("executable", "")),
                repair if row["outcome"] != "ENABLED" else "",
            )
        )
    return results
