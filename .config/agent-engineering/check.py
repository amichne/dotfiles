#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = []
# [tool.uv]
# no-build = true
# required-version = ">=0.12.9"
# [[tool.uv.index]]
# name = "pypi"
# url = "https://pypi.org/simple"
# default = true
# ///
"""Run existing local validators on files changed since a native session started."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

SUFFIXES = frozenset({".kt", ".md", ".mdx", ".txt"})
LIMIT = 16 * 1024 * 1024


class Status(StrEnum):
    PASSED = "passed"
    ADVISORY = "advisory"
    FAILED = "failed"
    NO_CHANGES = "no-changes"


class Rejected(Exception):
    """An explicit precondition or effect failure; never a passing check."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True).encode()


def object_value(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise Rejected("invalid-object")
    data = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in data):
        raise Rejected("invalid-key")
    return cast(dict[str, object], data)


def read_object(path: Path) -> dict[str, object]:
    if path.stat().st_size > LIMIT:
        raise Rejected("oversized-state")
    return object_value(json.loads(path.read_bytes()))


def string_map(value: object) -> dict[str, str]:
    data = object_value(value)
    if any(not isinstance(item, str) for item in data.values()):
        raise Rejected("invalid-snapshot")
    if any(
        Path(name).is_absolute()
        or ".." in Path(name).parts
        or Path(name).suffix.lower() not in SUFFIXES
        for name in data
    ):
        raise Rejected("invalid-snapshot-path")
    return cast(dict[str, str], data)


def atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        name = Path(handle.name)
        try:
            _ = handle.write(encoded(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
            _ = name.replace(path)
        finally:
            name.unlink(missing_ok=True)


def state_root() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    return base / "agent-engineering"


def git(cwd: Path, *arguments: str) -> bytes:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    # The public HOME checkout uses a separate bare Git directory.
    prefix = ["git", "-C", str(cwd)]
    if cwd == Path.home().resolve() and (cwd / ".dotfiles.git").is_dir():
        prefix += [f"--git-dir={cwd / '.dotfiles.git'}", f"--work-tree={cwd}"]
    result = subprocess.run(
        [*prefix, *arguments], capture_output=True, env=environment, timeout=20, check=False
    )
    if result.returncode:
        raise Rejected("git-failed")
    return result.stdout


def repository(cwd: Path) -> Path:
    return Path(os.fsdecode(git(cwd, "rev-parse", "--show-toplevel")).strip()).resolve()


def file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def snapshot(repo: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    inventory = git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for raw in inventory.split(b"\0"):
        if not raw:
            continue
        name = os.fsdecode(raw)
        if Path(name).suffix.lower() not in SUFFIXES:
            continue
        path = repo / name
        if not path.resolve().is_relative_to(repo) or path.is_symlink():
            raise Rejected("unsafe-source-path")
        if path.is_file() and path.stat().st_size > LIMIT:
            raise Rejected("oversized-input")
        values[name] = file_hash(path) if path.is_file() else "deleted"
    return values


def scope_signature(repo: Path) -> str:
    inventory = git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    paths = {
        repo / os.fsdecode(raw)
        for raw in inventory.split(b"\0")
        if raw and Path(os.fsdecode(raw)).name == ".gitignore"
    }
    paths.add(repo / ".gitignore")
    exclude = Path(os.fsdecode(git(repo, "rev-parse", "--git-path", "info/exclude")).strip())
    paths.add(exclude if exclude.is_absolute() else repo / exclude)
    return digest(
        encoded(
            [(str(path), file_hash(path) if path.is_file() else "absent") for path in sorted(paths)]
        )
    )


def changed(before: dict[str, str], after: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    )


@dataclass(frozen=True)
class Tools:
    kotlin: Path
    assessment: Path
    vale: Path

    @classmethod
    def parse(cls, value: object) -> Tools:
        data = object_value(value)
        if set(data) != {"kotlin", "assessment", "vale"}:
            raise Rejected("invalid-tools")
        paths: list[Path] = []
        for key in ("kotlin", "assessment", "vale"):
            item = data[key]
            if not isinstance(item, str) or not Path(item).is_absolute():
                raise Rejected("invalid-tool-path")
            paths.append(Path(item))
        return cls(*paths)

    def signature(self, kind: str) -> str:
        owner = self.kotlin if kind == "kotlin" else self.assessment
        files = [owner, Path(sys.executable).resolve(), Path(__file__).resolve()]
        if kind == "kotlin":
            files.append(owner.with_name(owner.name + ".lock"))
        else:
            # The existing assessment owns both adjacent scripts and its local policy.
            skill = owner.parent.parent
            if not (skill / "assets/vale/resources.lock.json").is_file():
                raise Rejected("missing-policy")
            files.extend(sorted((skill / "assets/vale").rglob("*")))
            files.extend(sorted(owner.parent.glob("*.py")))
            files.extend(sorted(owner.parent.glob("*.lock")))
            files.append(self.vale)
        selected = [path for path in files if not path.is_dir()]
        if not selected or not all(path.is_file() for path in selected):
            raise Rejected("missing-tool")
        return digest(encoded([(str(path), file_hash(path)) for path in selected]))


@dataclass(frozen=True)
class Result:
    status: Status
    report: dict[str, object]

    @classmethod
    def parse(cls, kind: str, code: int, payload: object) -> Result:
        data = object_value(payload)
        if kind == "kotlin":
            findings = data.get("findings")
            if (
                code != 0
                or data.get("ok") is not True
                or data.get("status") != "advisory"
                or not isinstance(findings, list)
            ):
                raise Rejected("invalid-kotlin-report")
            return cls(Status.ADVISORY if findings else Status.PASSED, data)
        if data.get("type") == "REJECTED" and code == 2:
            return cls(Status.FAILED, data)
        if (
            data.get("type") != "ASSESSED"
            or data.get("schemaVersion") != 2
            or code not in (0, 1)
            or not isinstance(data.get("documents"), list)
            or not data.get("documents")
        ):
            raise Rejected("invalid-assessment-report")
        return cls(Status.PASSED if code == 0 else Status.FAILED, data)


def invoke(arguments: list[str], kind: str, repo: Path) -> Result:
    with subprocess.Popen(
        arguments, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
    ) as process:
        try:
            stdout, _stderr = process.communicate(timeout=35)
            if len(stdout) > LIMIT:
                raise Rejected("oversized-report")
            return Result.parse(kind, process.returncode, json.loads(stdout))
        finally:
            # Cancel the whole validator group, including Vale children.
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                _ = process.communicate()


def kotlin_arguments(tools: Tools, repo: Path, names: tuple[str, ...]) -> list[str]:
    arguments = [sys.executable, str(tools.kotlin), "--repo", str(repo), "--format", "json"]
    for name in names:
        # The existing checker drops deleted files. A deleted file still selects
        # its surviving package peers and ancestors, without using its Git fallback.
        target = repo / name
        if not target.is_file():
            for directory in (target.parent, *target.parent.parents):
                if not directory.is_relative_to(repo):
                    break
                peers = sorted(directory.glob("*.kt"))
                if peers:
                    target = peers[0]
                    break
        arguments.extend(["--changed-file", str(target)])
    return arguments


def check(repo: Path, directory: Path, retry: bool) -> dict[str, object]:
    state = read_object(directory / "session.json")
    if state.get("repo") != str(repo):
        raise Rejected("session-repository-mismatch")
    if state.get("scope") != scope_signature(repo):
        raise Rejected("ignore-scope-changed; inspect explicit file scope before handoff")
    before = string_map(state.get("baseline"))
    after = snapshot(repo)
    selected = changed(before, after)
    results: dict[str, object] = {}
    tools: Tools | None = None
    for kind in ("kotlin", "prose"):
        names = tuple(
            name for name in selected if (Path(name).suffix == ".kt") == (kind == "kotlin")
        )
        if kind == "prose":
            names = tuple(name for name in names if (repo / name).is_file())
        if not names:
            results[kind] = {"status": Status.NO_CHANGES, "files": []}
            continue
        try:
            if tools is None:
                tools = Tools.parse(read_object(state_root() / "tools.json"))
            signature = tools.signature(kind)
            # Package topology is an input to the layout heuristic. It reads names,
            # not Kotlin bodies. All session edits remain selected after a commit.
            topology = (
                sorted(name for name in after if name.endswith(".kt") and after[name] != "deleted")
                if kind == "kotlin"
                else []
            )
            key = digest(
                encoded([signature, [(name, after.get(name)) for name in names], topology])
            )
            receipt = directory / (kind + ".json")
            cached = read_object(receipt) if receipt.is_file() else {}
            if not retry and cached.get("key") == key:
                results[kind] = {**cached, "cached": True}
                continue
            try:
                if kind == "kotlin":
                    result = invoke(kotlin_arguments(tools, repo, names), kind, repo)
                else:
                    result = invoke(
                        [
                            sys.executable,
                            str(tools.assessment),
                            "--vale-bin",
                            str(tools.vale),
                            *[str(repo / name) for name in names],
                        ],
                        kind,
                        repo,
                    )
            except (Rejected, OSError, ValueError, subprocess.SubprocessError) as error:
                result = Result(Status.FAILED, {"failure": str(error)[:300]})
            if snapshot(repo) != after or tools.signature(kind) != signature:
                raise Rejected("input-changed-during-check")
            record: dict[str, object] = {
                "key": key,
                "inputs": {name: after.get(name) for name in names},
                "toolSignature": signature,
                "validator": str(tools.kotlin if kind == "kotlin" else tools.assessment),
                "topologySha256": digest(encoded(topology)),
                "status": result.status,
                "files": list(names),
                "report": result.report,
                "cached": False,
            }
            atomic_write(receipt, record)
            results[kind] = record
        except (Rejected, OSError, ValueError, subprocess.SubprocessError) as error:
            results[kind] = {
                "status": Status.FAILED,
                "files": list(names),
                "failure": str(error)[:300],
            }
    failed = any(object_value(value).get("status") == Status.FAILED for value in results.values())
    no_changes = all(
        object_value(value).get("status") == Status.NO_CHANGES for value in results.values()
    )
    status = Status.FAILED if failed else Status.NO_CHANGES if no_changes else Status.PASSED
    report: dict[str, object] = {
        "status": status,
        "checks": results,
        "receipt": str(directory / "latest.json"),
    }
    atomic_write(directory / "latest.json", report)
    return report


@contextmanager
def session_lock(directory: Path) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def session_directory(repo: Path, session: str) -> Path:
    if not session or len(session) > 512:
        raise Rejected("invalid-session")
    return state_root() / "sessions" / digest(encoded([str(repo), session]))


def begin(repo: Path, directory: Path) -> dict[str, object]:
    target = directory / "session.json"
    if target.exists():
        if read_object(target).get("repo") != str(repo):
            raise Rejected("session-repository-mismatch")
        return {"status": "existing-session", "receipt": str(target)}
    atomic_write(
        target, {"repo": str(repo), "baseline": snapshot(repo), "scope": scope_signature(repo)}
    )
    return {"status": "started", "receipt": str(target)}


def codex_response(report: dict[str, object]) -> dict[str, object]:
    message = (
        "agent-check: "
        + str(report.get("status"))
        + "; receipt="
        + str(report.get("receipt", "unavailable"))
    )
    if report.get("status") == Status.FAILED:
        return {"continue": False, "stopReason": message, "systemMessage": message}
    return {"systemMessage": message}


def inspect_resources() -> dict[str, object]:
    home = Path.home()
    source = home / ".config/agent-engineering/B0.md"
    source_hash = file_hash(source)
    resources: list[dict[str, object]] = []
    for agent in (home / ".codex", home / ".pi/agent"):
        path = agent / "AGENTS.md"
        resources.append(
            {
                "path": str(path),
                "sha256": file_hash(path) if path.is_file() else None,
                "matchesSource": path.is_file() and file_hash(path) == source_hash,
                "overridePresent": (agent / "AGENTS.override.md").exists(),
            }
        )
    config = state_root() / "tools.json"
    return {
        "status": "inspected",
        "source": str(source),
        "sha256": source_hash,
        "resources": resources,
        "tools": read_object(config) if config.is_file() else "not-configured",
        "qualification": "file-inventory-only; use native host inspection for effective selection",
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    _ = result.add_argument("--self-test", action="store_true")
    commands = result.add_subparsers(dest="command")
    setup = commands.add_parser(
        "configure", help="Record explicit local validator paths; never install tools."
    )
    for name in ("kotlin", "assessment", "vale"):
        _ = setup.add_argument("--" + name, required=True, type=Path)
    for name in ("begin", "turn", "handoff", "status"):
        command = commands.add_parser(name)
        _ = command.add_argument("--repo", type=Path, default=Path.cwd())
        _ = command.add_argument("--session", required=True)
        _ = command.add_argument("--retry", action="store_true")
    _ = commands.add_parser("codex", help="Read a native SessionStart or Stop event from stdin.")
    _ = commands.add_parser(
        "inspect", help="Show public B0 provenance and explicit validator selection."
    )
    return result


def main() -> int:
    args = parser().parse_args()
    report: dict[str, object]
    native = args.command == "codex"
    try:
        if args.self_test:
            if changed({"a.md": "old"}, {"a.md": "new"}) != ("a.md",):
                raise Rejected("self-test-failed")
            print('{"status":"passed"}')
            return 0
        if args.command is None:
            raise Rejected("missing-command")
        if args.command == "inspect":
            report = inspect_resources()
        elif args.command == "configure":
            tools = Tools(args.kotlin.resolve(), args.assessment.resolve(), args.vale.resolve())
            _ = tools.signature("kotlin")
            _ = tools.signature("prose")
            atomic_write(
                state_root() / "tools.json",
                {
                    "kotlin": str(tools.kotlin),
                    "assessment": str(tools.assessment),
                    "vale": str(tools.vale),
                },
            )
            report = {"status": "configured"}
        else:
            command: str = args.command
            if native:
                payload = object_value(json.loads(sys.stdin.read(LIMIT + 1)))
                event = payload.get("hook_event_name")
                command = {"SessionStart": "begin", "Stop": "handoff"}.get(str(event), "invalid")
                cwd, session = payload.get("cwd"), payload.get("session_id")
                if command == "invalid" or not isinstance(cwd, str) or not isinstance(session, str):
                    raise Rejected("invalid-native-event")
                repo, session_id, retry = repository(Path(cwd)), session, False
            else:
                repo, session_id, retry = repository(args.repo.resolve()), args.session, args.retry
            directory = session_directory(repo, session_id)
            with session_lock(directory):
                try:
                    if command == "begin":
                        report = begin(repo, directory)
                    elif command == "status":
                        report = {
                            **read_object(directory / "latest.json"),
                            "freshness": "last-recorded; run handoff for current inputs",
                        }
                    else:
                        report = check(repo, directory, retry)
                except (
                    Rejected,
                    OSError,
                    ValueError,
                    subprocess.SubprocessError,
                    KeyboardInterrupt,
                ) as error:
                    report = {
                        "status": Status.FAILED,
                        "failure": str(error)[:300],
                        "receipt": str(directory / "latest.json"),
                    }
                    atomic_write(directory / "latest.json", report)
    except (Rejected, OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        report = {"status": Status.FAILED, "failure": str(error)[:300]}
    print(json.dumps(codex_response(report) if native else report, sort_keys=True))
    return 0 if native or report.get("status") != Status.FAILED else 1


if __name__ == "__main__":

    def cancelled(_number: int, _frame: object) -> None:
        raise KeyboardInterrupt("cancelled")

    _ = signal.signal(signal.SIGTERM, cancelled)
    raise SystemExit(main())
