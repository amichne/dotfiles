#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["jsonschema==4.26.0"]
# [tool.uv]
# no-build = true
# required-version = ">=0.12.9"
# [[tool.uv.index]]
# name = "pypi"
# url = "https://pypi.org/simple"
# default = true
# ///
"""Run local validators on explicit files without repository discovery or snapshots."""

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
from typing import Protocol, cast

import resources
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SUFFIXES = frozenset({".kt", ".md", ".mdx", ".txt"})
# Admission matches the recovered checker's SOURCE_ROOT_PARTS at the qualified revision.
KOTLIN_ROOTS = frozenset(
    {("src", "main", "kotlin"), ("src", "test", "kotlin"), ("src", "integrationTest", "kotlin")}
)
LIMIT = 16 * 1024 * 1024
ASSESSMENT_SCHEMA_SHA256 = "c1913e1dbfb63c5df2518456e23f52c25c7cd08c8ae0bbe4f257c101c0f630ac"
RESTORED_SCHEMA_SHA256 = "65f8c2174a98d90066245a2002b3fbca7cfd04b3ed3b7783b1e41e9ab34382ff"


class Status(StrEnum):
    PASSED = "passed"
    ADVISORY = "advisory"
    FAILED = "failed"
    NO_CHANGES = "no-changes"


class Rejected(Exception):
    """An explicit precondition or effect failure; never a passing check."""


class SchemaValidator(Protocol):
    # jsonschema's public validate API accepts an arbitrary Python instance.
    # The pinned stubs leave that method variadic; keep that boundary local.
    def validate(self, instance: object) -> None: ...


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


def working_directory(cwd: Path) -> Path:
    directory = cwd.resolve(strict=True)
    if not directory.is_dir():
        raise Rejected("invalid-working-directory")
    return directory


def file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


@dataclass(frozen=True)
class FileScope:
    root: Path
    names: tuple[str, ...]

    @classmethod
    def parse(cls, root: Path, values: list[str]) -> FileScope:
        names: set[str] = set()
        for value in values:
            path = Path(value)
            if path.is_absolute():
                if not path.is_relative_to(root):
                    raise Rejected("outside-file-scope")
                path = path.relative_to(root)
            if (
                not path.parts
                or ".." in path.parts
                or {".git", ".dotfiles.git"}.intersection(path.parts)
                or path.suffix not in SUFFIXES
            ):
                raise Rejected("unsupported-source-path")
            names.add(path.as_posix())
        return cls(root, tuple(sorted(names)))

    def fingerprints(self) -> dict[str, str | None]:
        values: dict[str, str | None] = {}
        for name in self.names:
            path = self.root / name
            for part in (path, *path.parents):
                if part.is_symlink():
                    raise Rejected("unsafe-source-path")
                if part == self.root:
                    break
            if path.exists():
                if not path.is_file():
                    raise Rejected("non-file-source")
                if path.stat().st_size > LIMIT:
                    raise Rejected("oversized-input")
                values[name] = file_hash(path)
            else:
                values[name] = None
        return values


def select_files(repo: Path, directory: Path, requested: list[str]) -> FileScope:
    target = directory / "selection.json"
    previous: list[str] = []
    if target.exists():
        state = read_object(target)
        if state.get("root") != str(repo):
            raise Rejected("session-workspace-mismatch")
        raw = state.get("files")
        if not isinstance(raw, list):
            raise Rejected("invalid-file-selection")
        for item in cast(list[object], raw):
            if not isinstance(item, str):
                raise Rejected("invalid-file-selection")
            previous.append(item)
    scope = FileScope.parse(repo, [*previous, *requested])
    _ = scope.fingerprints()
    # Keep explicit obligations before validators run. Later native events reuse this scope.
    atomic_write(target, {"root": str(repo), "files": list(scope.names)})
    return scope


@dataclass(frozen=True)
class Tools:
    kotlin: Path
    assessment: Path
    vale: Path

    def prose_version(self) -> int:
        schema = self.assessment.parent.parent / "references/text-assessment.schema.json"
        versions = {ASSESSMENT_SCHEMA_SHA256: 2, RESTORED_SCHEMA_SHA256: 1}
        version = versions.get(file_hash(schema))
        if version is None:
            raise Rejected("unsupported-assessment-schema")
        return version

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
        files = [
            owner,
            Path(sys.executable).resolve(),
            Path(__file__).resolve(),
            Path(__file__).with_suffix(".py.lock"),
        ]
        files.extend(sorted(Path(__file__).parent.glob("*.py")))
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
            files.extend(sorted((skill / "references").glob("*.json")))
            _ = self.prose_version()
            files.append(self.vale)
        selected = [path for path in files if not path.is_dir()]
        if not selected or not all(path.is_file() for path in selected):
            raise Rejected("missing-tool")
        return digest(
            encoded([(str(path), file_hash(path), path.stat().st_mode) for path in selected])
        )


@dataclass(frozen=True)
class Result:
    status: Status
    report: dict[str, object]

    @classmethod
    def parse(
        cls,
        kind: str,
        code: int,
        payload: object,
        tools: Tools,
        inputs: dict[str, str],
        glossary: tuple[Path, str] | None = None,
    ) -> Result:
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
        skill = tools.assessment.parent.parent
        schema = skill / "references/text-assessment.schema.json"
        # Qualify the owner's real schema, with internal references only and no network resolver.
        version = tools.prose_version()
        try:
            validator = cast(SchemaValidator, Draft202012Validator(read_object(schema)))
            validator.validate(data)
        except ValidationError as error:
            raise Rejected("invalid-assessment-report") from error
        if data["type"] == "REJECTED":
            if code != 2:
                raise Rejected("inconsistent-assessment-exit")
            return cls(Status.FAILED, data)
        engine = object_value(data["engine"])
        if engine["policySha256"] != file_hash(skill / "assets/vale/resources.lock.json"):
            raise Rejected("assessment-policy-mismatch")
        documents = cast(list[object], data["documents"])
        observed: dict[str, str] = {}
        has_findings = False
        for value in documents:
            document = object_value(value)
            name = cast(str, document["path"])
            if name in observed:
                raise Rejected("duplicate-assessment-document")
            observed[name] = cast(str, document["sourceSha256"])
            has_findings = has_findings or bool(document["findings"])
        if observed != inputs:
            raise Rejected("assessment-input-mismatch")
        if version == 1:
            terminology = object_value(data["glossary"])
            if data["type"] == "INCOMPLETE":
                if code != 2 or glossary is not None:
                    raise Rejected("inconsistent-incomplete-assessment")
                return cls(Status.FAILED, data)
            if glossary is None or terminology.get("sourceSha256") != glossary[1]:
                raise Rejected("assessment-glossary-mismatch")
        if code != (1 if has_findings else 0):
            raise Rejected("inconsistent-assessment-exit")
        return cls(Status.PASSED if code == 0 else Status.FAILED, data)


def finite_json(constant: str) -> object:
    raise Rejected("nonfinite-json-number: " + constant)


def invoke(
    arguments: list[str],
    kind: str,
    repo: Path,
    tools: Tools,
    inputs: dict[str, str],
    glossary: tuple[Path, str] | None = None,
) -> Result:
    with subprocess.Popen(
        arguments, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
    ) as process:
        try:
            stdout, _stderr = process.communicate(timeout=35)
            if len(stdout) > LIMIT:
                raise Rejected("oversized-report")
            return Result.parse(
                kind,
                process.returncode,
                json.loads(stdout, parse_constant=finite_json),
                tools,
                inputs,
                glossary,
            )
        finally:
            # Cancel the whole validator group, including Vale children.
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                _ = process.communicate()


def kotlin_targets(repo: Path, names: tuple[str, ...]) -> tuple[Path, ...]:
    targets: list[Path] = []
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
                if tuple(directory.parts[-3:]) in KOTLIN_ROOTS:
                    break
        targets.append(target)
    return tuple(targets)


def layout_topology(repo: Path, names: tuple[str, ...]) -> list[object]:
    directories: set[Path] = set()
    for target in kotlin_targets(repo, names):
        if not target.is_file():
            continue
        for directory in target.parents:
            if not directory.is_relative_to(repo):
                break
            directories.add(directory)
            if tuple(directory.parts[-3:]) in KOTLIN_ROOTS:
                break
    result: list[object] = []
    # The recovered heuristic reads direct files and each parent's siblings.
    # Its read set includes ignored/generated peer names.
    for directory in sorted(directories):
        for sibling in sorted(directory.parent.iterdir()):
            if sibling.is_dir():
                if not sibling.resolve().is_relative_to(repo):
                    raise Rejected("unsafe-layout-directory")
                peers = [(path.name, path.is_file()) for path in sorted(sibling.glob("*.kt"))]
                result.append((str(sibling.relative_to(repo)), peers))
    return result


def kotlin_arguments(tools: Tools, repo: Path, names: tuple[str, ...]) -> list[str]:
    arguments = [sys.executable, str(tools.kotlin), "--repo", str(repo), "--format", "json"]
    for target in kotlin_targets(repo, names):
        arguments.extend(["--changed-file", str(target)])
    return arguments


def glossary_input(repo: Path) -> tuple[Path, str] | None:
    # Prefer a canonical JSON source over its generated Markdown reader view.
    # No discovery outside these explicit repository paths, and no invented terms.
    for candidates in (
        ("glossary.json", "docs/glossary.json"),
        ("GLOSSARY.md", "docs/GLOSSARY.md"),
    ):
        selected = [repo / name for name in candidates if (repo / name).exists()]
        if len(selected) > 1:
            raise Rejected("ambiguous-repository-glossary")
        if selected:
            path = selected[0]
            if (
                path.is_symlink()
                or not path.resolve().is_relative_to(repo)
                or not path.is_file()
                or path.stat().st_size > LIMIT
            ):
                raise Rejected("unsafe-repository-glossary")
            return path, file_hash(path)
    return None


def check(scope: FileScope, directory: Path, retry: bool) -> dict[str, object]:
    repo = scope.root
    after = scope.fingerprints()
    selected = scope.names
    if not selected:
        report: dict[str, object] = {
            "status": "not-applicable",
            "reason": "no-explicit-files",
            "receipt": str(directory / "latest.json"),
        }
        atomic_write(directory / "latest.json", report)
        return report
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
            if kind == "kotlin" and any(
                not any(
                    tuple(Path(name).parts[index : index + 3]) in KOTLIN_ROOTS
                    for index in range(len(Path(name).parts) - 2)
                )
                for name in names
            ):
                raise Rejected("unsupported-kotlin-source-root")
            if tools is None:
                tools = Tools.parse(read_object(state_root() / "tools.json"))
            signature = tools.signature(kind)
            glossary = (
                glossary_input(repo) if kind == "prose" and tools.prose_version() == 1 else None
            )
            # Package topology is an input to the layout heuristic. It reads names,
            # not Kotlin bodies. Explicit selections stay scoped across later events.
            topology = layout_topology(repo, names) if kind == "kotlin" else []
            key = digest(
                encoded(
                    [
                        signature,
                        [(name, after.get(name)) for name in names],
                        topology,
                        [str(glossary[0]), glossary[1]] if glossary else None,
                    ]
                )
            )
            receipt = directory / (kind + ".json")
            cached = read_object(receipt) if receipt.is_file() else {}
            if not retry and cached.get("key") == key:
                results[kind] = {**cached, "cached": True}
                continue
            try:
                if kind == "kotlin":
                    result = invoke(kotlin_arguments(tools, repo, names), kind, repo, tools, {})
                else:
                    inputs: dict[str, str] = {}
                    for name in names:
                        fingerprint = after[name]
                        if fingerprint is None:
                            raise Rejected("input-changed-before-check")
                        inputs[str(repo / name)] = fingerprint
                    result = invoke(
                        [
                            sys.executable,
                            str(tools.assessment),
                            "--vale-bin",
                            str(tools.vale),
                            *(["--glossary", str(glossary[0])] if glossary else []),
                            *[str(repo / name) for name in names],
                        ],
                        kind,
                        repo,
                        tools,
                        inputs,
                        glossary,
                    )
            except (Rejected, OSError, ValueError, subprocess.SubprocessError) as error:
                result = Result(Status.FAILED, {"failure": str(error)[:300]})
            if (
                scope.fingerprints() != after
                or tools.signature(kind) != signature
                or (kind == "kotlin" and layout_topology(repo, names) != topology)
                or (
                    kind == "prose"
                    and tools.prose_version() == 1
                    and glossary_input(repo) != glossary
                )
            ):
                raise Rejected("input-changed-during-check")
            record: dict[str, object] = {
                "key": key,
                "inputs": {name: after.get(name) for name in names},
                "toolSignature": signature,
                "validator": str(tools.kotlin if kind == "kotlin" else tools.assessment),
                "topologySha256": digest(encoded(topology)),
                "glossary": {"path": str(glossary[0]), "sha256": glossary[1]} if glossary else None,
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
    advisory = any(
        object_value(value).get("status") == Status.ADVISORY for value in results.values()
    )
    status = (
        Status.FAILED
        if failed
        else Status.NO_CHANGES
        if no_changes
        else Status.ADVISORY
        if advisory
        else Status.PASSED
    )
    report = {
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


def begin(scope: FileScope, directory: Path) -> dict[str, object]:
    return {
        "status": "started" if scope.names else "not-applicable",
        **({} if scope.names else {"reason": "no-explicit-files"}),
        "files": list(scope.names),
        "receipt": str(directory / "selection.json"),
    }


def codex_response(report: dict[str, object]) -> dict[str, object]:
    message = (
        "agent-check: "
        + str(report.get("status"))
        + ("; " + str(report["reason"]) if "reason" in report else "")
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
    config = state_root() / "tools.json"
    return {
        "status": "inspected",
        "source": str(source),
        "sha256": source_hash,
        "resources": resources.inventory(home, source.parent),
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
    install = commands.add_parser(
        "install",
        help="Plan or apply a preserving B0/native resource migration; never change trust/settings.",
    )
    for name in ("kotlin", "assessment", "vale"):
        _ = install.add_argument("--" + name, required=True, type=Path)
    _ = install.add_argument("--apply", action="store_true")
    _ = install.add_argument("--expected-plan", default="")
    for name in ("begin", "turn", "handoff", "status"):
        command = commands.add_parser(name)
        _ = command.add_argument("--repo", type=Path, default=Path.cwd())
        _ = command.add_argument("--session", required=True)
        _ = command.add_argument("--retry", action="store_true")
        _ = command.add_argument(
            "--file",
            action="append",
            default=[],
            help="Explicit file path. Repeat to select more files.",
        )
        _ = command.add_argument(
            "--native",
            action="store_true",
            help="Native lifecycle adapter: report an empty explicit scope without a failure.",
        )
    codex = commands.add_parser(
        "codex", help="Read a native SessionStart or Stop event from stdin."
    )
    _ = codex.add_argument(
        "--file", action="append", default=[], help="Explicit native file scope."
    )
    _ = commands.add_parser(
        "inspect", help="Show public B0 provenance and explicit validator selection."
    )
    return result


def main() -> int:
    args = parser().parse_args()
    report: dict[str, object]
    codex = args.command == "codex"
    native = codex or bool(getattr(args, "native", False))
    try:
        if args.self_test:
            scope = FileScope.parse(Path("/workspace"), ["README.md", "README.md"])
            if scope.names != ("README.md",):
                raise Rejected("self-test-failed")
            try:
                _ = FileScope.parse(Path("/workspace"), ["../outside.md"])
            except Rejected:
                pass
            else:
                raise Rejected("self-test-failed")
            print('{"status":"passed"}')
            return 0
        if args.command is None:
            raise Rejected("missing-command")
        if args.command == "inspect":
            report = inspect_resources()
        elif args.command in ("configure", "install"):
            tools = Tools(args.kotlin.resolve(), args.assessment.resolve(), args.vale.resolve())
            signature = digest(encoded([tools.signature("kotlin"), tools.signature("prose")]))
            selected = {
                "kotlin": str(tools.kotlin),
                "assessment": str(tools.assessment),
                "vale": str(tools.vale),
            }
            if args.command == "install":
                directory = state_root()
                with session_lock(directory / "installation-lock"):
                    plan = resources.build_plan(
                        Path.home(), Path(__file__).resolve().parent, directory, selected, signature
                    )
                    report = (
                        resources.apply_plan(plan, args.expected_plan, directory)
                        if args.apply
                        else plan.report()
                    )
                print(json.dumps(report, sort_keys=True))
                return 0
            atomic_write(
                state_root() / "tools.json",
                selected,
            )
            report = {"status": "configured"}
        else:
            command: str = args.command
            if codex:
                payload = object_value(json.loads(sys.stdin.read(LIMIT + 1)))
                event = payload.get("hook_event_name")
                command = {"SessionStart": "begin", "Stop": "handoff"}.get(str(event), "invalid")
                cwd, session = payload.get("cwd"), payload.get("session_id")
                if command == "invalid" or not isinstance(cwd, str) or not isinstance(session, str):
                    raise Rejected("invalid-native-event")
                working, session_id, retry = Path(cwd), session, False
                requested: list[str] = args.file
            else:
                working, session_id, retry = args.repo.resolve(), args.session, args.retry
                requested = args.file
            repo = working_directory(working)
            directory = session_directory(repo, session_id)
            with session_lock(directory):
                try:
                    if command == "begin":
                        report = begin(select_files(repo, directory, requested), directory)
                    elif command == "status":
                        report = {
                            **read_object(directory / "latest.json"),
                            "freshness": "last-recorded; run handoff for current inputs",
                        }
                    else:
                        report = check(select_files(repo, directory, requested), directory, retry)
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
    print(json.dumps(codex_response(report) if codex else report, sort_keys=True))
    return 0 if native or report.get("status") != Status.FAILED else 1


if __name__ == "__main__":

    def cancelled(_number: int, _frame: object) -> None:
        raise KeyboardInterrupt("cancelled")

    _ = signal.signal(signal.SIGTERM, cancelled)
    raise SystemExit(main())
