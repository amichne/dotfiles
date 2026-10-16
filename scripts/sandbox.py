#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = []
# [tool.uv]
# no-build = true
# [[tool.uv.index]]
# name = "pypi"
# url = "https://pypi.org/simple"
# default = true
# ///
"""Run the public Dotfiles source in a disposable, offline Docker container."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BUILD_FILES: tuple[str, ...] = (
    "containers/Dockerfile",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
)


@dataclass(frozen=True, slots=True)
class Rejected:
    reason: Literal["unsafe-source", "not-source-root", "git-failed", "empty-source"]
    detail: str
    status: int = 2


@dataclass(frozen=True, slots=True)
class PublicFile:
    name: str
    content: bytes
    mode: int


class Arguments(argparse.Namespace):
    source: Path
    action: Literal["snapshot", "build", "check", "shell", "run"] | None
    output: Path
    command: list[str]
    self_test: bool


def source_files(root: Path) -> tuple[PublicFile, ...] | Rejected:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    git = ["git", "-c", "core.fsmonitor=false", "-C", str(root)]
    if (root / ".dotfiles.git").is_dir():
        git = [
            "git",
            "-c",
            "core.fsmonitor=false",
            f"--git-dir={root / '.dotfiles.git'}",
            f"--work-tree={root}",
        ]
    else:
        top = subprocess.run(
            [*git, "rev-parse", "--show-toplevel"], env=env, capture_output=True, check=False
        )
        if top.returncode or Path(os.fsdecode(top.stdout).strip()).resolve() != root:
            return Rejected("not-source-root", str(root))
    result = subprocess.run(
        [*git, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        env=env,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return Rejected("git-failed", os.fsdecode(result.stderr), result.returncode)
    ignored = subprocess.run(
        [*git, "ls-files", "--cached", "--ignored", "--exclude-standard", "-z"],
        env=env,
        capture_output=True,
        check=False,
    )
    if ignored.returncode:
        return Rejected("git-failed", os.fsdecode(ignored.stderr), ignored.returncode)
    files: list[PublicFile] = []
    for raw in sorted(set(result.stdout.split(b"\0")) - set(ignored.stdout.split(b"\0")) - {b""}):
        name = os.fsdecode(raw)
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            return Rejected("unsafe-source", name)
        if {".git", ".dotfiles.git"}.intersection(path.parts):
            return Rejected("unsafe-source", name)
        current = root
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                return Rejected("unsafe-source", name)
        if not current.exists():
            continue
        if not current.is_file():
            return Rejected("unsafe-source", name)
        mode = 0o755 if current.stat().st_mode & 0o111 else 0o644
        files.append(PublicFile(name, current.read_bytes(), mode))
    return tuple(files) if files else Rejected("empty-source", str(root))


def write_snapshot(files: tuple[PublicFile, ...], output: Path) -> None:
    with output.open("xb") as stream, tarfile.open(fileobj=stream, mode="w") as archive:
        for file in files:
            info = tarfile.TarInfo("src/" + file.name)
            info.size = len(file.content)
            info.mode = file.mode
            info.uid = info.gid = 10001
            archive.addfile(info, io.BytesIO(file.content))


def build_image(files: tuple[PublicFile, ...], proxy_ca: Path | None) -> str:
    selected = {file.name: file for file in files}
    digest = hashlib.sha256()
    with tempfile.TemporaryDirectory(prefix="dotfiles-build-") as directory:
        context = Path(directory)
        for name in BUILD_FILES:
            file = selected[name]
            digest.update(name.encode() + b"\0" + file.content)
            destination = "Dockerfile" if name == "containers/Dockerfile" else name
            _ = (context / destination).write_bytes(file.content)
        tag = "dotfiles-sandbox:" + digest.hexdigest()[:16]
        secrets = ["--secret", f"id=proxy_ca,src={proxy_ca}"] if proxy_ca is not None else []
        _ = subprocess.run(["docker", "build", *secrets, "--tag", tag, str(context)], check=True)
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", tag],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def run_container(image: str, archive: Path, command: tuple[str, ...], interactive: bool) -> int:
    name = "dotfiles-sandbox-" + uuid4().hex
    arguments = [
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        name,
        "--label",
        "amichne.dotfiles.sandbox=true",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=256",
        "--memory=2g",
        "--cpus=2",
        "--init",
        "--tmpfs=/work:rw,exec,nosuid,nodev,uid=10001,gid=10001,mode=0700,size=768m",
        "--tmpfs=/tmp:rw,exec,nosuid,nodev,mode=1777,size=256m",
    ]
    # Docker can inject proxy defaults. The offline process needs no proxy credentials.
    for variable in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        arguments.extend(("--env", variable + "=", "--env", variable.lower() + "="))
    arguments.extend((image, "sleep", "infinity"))
    print(f"sandbox: image={image} container={name}", flush=True)
    try:
        _ = subprocess.run(arguments, stdout=subprocess.DEVNULL, check=True)
        _ = subprocess.run(["docker", "exec", name, "mkdir", "/work/src"], check=True)
        with archive.open("rb") as stream:
            _ = subprocess.run(
                ["docker", "exec", "--interactive", name, "tar", "-xf", "-", "-C", "/work"],
                stdin=stream,
                check=True,
            )
        # This Git index belongs only to the copied source. No host metadata enters the container.
        setup = 'mkdir -p "$HOME"; git init --quiet; git add --all; '
        setup += "git -c user.name=Sandbox -c user.email=sandbox@example.invalid "
        setup += "-c commit.gpgsign=false commit --quiet -m Snapshot"
        _ = subprocess.run(
            ["docker", "exec", "--workdir", "/work/src", name, "/bin/sh", "-ec", setup],
            check=True,
        )
        terminal = ["--interactive", "--tty"] if interactive and sys.stdin.isatty() else []
        return subprocess.run(
            ["docker", "exec", *terminal, "--workdir", "/work/src", name, *command], check=False
        ).returncode
    finally:
        cleanup = subprocess.run(
            ["docker", "rm", "--force", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if cleanup.returncode:
            print(f"sandbox: examine cleanup for {name}", file=sys.stderr)


def interrupted(_number: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--source", type=Path, default=ROOT)
    _ = parser.add_argument("--self-test", action="store_true")
    actions = parser.add_subparsers(dest="action")
    snapshot = actions.add_parser(
        "snapshot", help="Copy Git-selected public files to a new tar file."
    )
    _ = snapshot.add_argument("output", type=Path)
    _ = actions.add_parser("build", help="Prepare the dependency image.")
    _ = actions.add_parser("check", help="Run scripts/check.sh in a disposable container.")
    _ = actions.add_parser("shell", help="Start Bash in a disposable container.")
    run = actions.add_parser("run", help="Run a literal command in a disposable container.")
    _ = run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(namespace=Arguments())
    if args.self_test:
        with tempfile.TemporaryDirectory(prefix="dotfiles-self-test-") as directory:
            output = Path(directory) / "source.tar"
            write_snapshot((PublicFile("literal file", b"content", 0o644),), output)
            with tarfile.open(output) as archive:
                if archive.getnames() != ["src/literal file"]:
                    return 1
        print("sandbox: self-test passed")
        return 0
    if args.action is None:
        parser.error("choose snapshot, build, check, shell, or run")
    command = ("./scripts/check.sh",)
    if args.action == "shell":
        command = ("/bin/bash", "--noprofile", "--norc")
    elif args.action == "run":
        command = tuple(args.command[1:] if args.command[:1] == ["--"] else args.command)
        if not command:
            parser.error("run needs a command after --")
    files = source_files(args.source.resolve())
    if isinstance(files, Rejected):
        print(f"sandbox: {files.reason}: {files.detail}", file=sys.stderr)
        return files.status
    if args.action == "snapshot":
        write_snapshot(files, args.output)
        return 0
    if shutil.which("docker") is None:
        print("sandbox: missing dependency: docker", file=sys.stderr)
        return 69
    missing = set(BUILD_FILES) - {file.name for file in files}
    if missing:
        print("sandbox: missing build inputs: " + ", ".join(sorted(missing)), file=sys.stderr)
        return 66
    certificate = os.environ.get("CODEX_PROXY_CERT")
    proxy_ca = Path(certificate).resolve() if certificate else None
    if proxy_ca is not None and not proxy_ca.is_file():
        print("sandbox: missing CODEX_PROXY_CERT file", file=sys.stderr)
        return 66
    image = build_image(files, proxy_ca)
    if args.action == "build":
        print(image)
        return 0
    with tempfile.TemporaryDirectory(prefix="dotfiles-snapshot-") as directory:
        archive = Path(directory) / "source.tar"
        write_snapshot(files, archive)
        print(
            "sandbox: source-sha256=" + hashlib.sha256(archive.read_bytes()).hexdigest(), flush=True
        )
        return run_container(image, archive, command, args.action == "shell")


if __name__ == "__main__":
    _ = signal.signal(signal.SIGTERM, interrupted)
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error
    except OSError as error:
        print(f"sandbox: io-error: {error}", file=sys.stderr)
        raise SystemExit(74) from error
    except KeyboardInterrupt:
        raise SystemExit(130) from None
