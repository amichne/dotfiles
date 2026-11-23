from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = ROOT / ".dotfiles"
# Python tooling runs from SUPPORT; HOME-root commands stay relative to ROOT.
PYTHON_SOURCE = (
    "scripts",
    "tests",
    "../.local/bin/keys",
    "../.local/bin/setup-tools",
    "../.local/bin/austincomplete",
    "../.local/bin/claude-worktree",
    "../.local/bin/worktrunk-commit-message",
)
SHELL_SOURCE = (
    ".agents/setup",
    ".agents/resume",
    ".local/bin/dotfiles",
    ".local/bin/git-recents",
    ".local/bin/shell-prompt",
    ".dotfiles/scripts/check.sh",
)

# `node --check` parses .ts as JavaScript on some Node releases. Strip types with
# Node's own API, then check the JavaScript syntax, so the result does not depend
# on the installed Node version.
TYPESCRIPT_CHECK = """
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { spawnSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
const directory = mkdtempSync(path.join(os.tmpdir(), 'ts-check-'));
let status = 0;
for (const file of process.argv.slice(1)) {
  const stripped = path.join(directory, path.basename(file) + '.mjs');
  writeFileSync(stripped, stripTypeScriptTypes(readFileSync(file, 'utf8')));
  const result = spawnSync(process.execPath, ['--check', stripped], { stdio: 'inherit' });
  if (result.status) { console.error(`syntax check failed: ${file}`); status = result.status; }
}
rmSync(directory, { recursive: true, force: true });
process.exit(status);
"""
TYPESCRIPT_SOURCE = (
    ".pi/agent/extensions/deepen.ts",
    ".pi/agent/extensions/ask-questions.ts",
    ".pi/agent/lib/questions.ts",
)


def run(arguments: list[str], env: dict[str, str], cwd: Path = ROOT) -> int:
    print("==> " + " ".join(arguments), flush=True)
    return subprocess.run(arguments, cwd=cwd, env=env, check=False).returncode


def main() -> int:
    for name in ("uv", "node", "zsh", "shellcheck", "git", "nvim"):
        if shutil.which(name) is None:
            print(f"check: missing dependency: {name}", file=sys.stderr)
            return 69
    node = subprocess.run(
        ["node", "-p", "process.execPath"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if node.returncode:
        print(node.stderr, file=sys.stderr)
        return node.returncode
    env = {
        **os.environ,
        "DOTFILES_TEST_NODE": node.stdout.strip(),
        "DOTFILES_TEST_UV": str(Path(shutil.which("uv") or "uv").resolve()),
    }
    ruff = ["uv", "run", "--locked", "ruff"]
    python_commands = [
        [*ruff, "format", "--check", "--config", "pyproject.toml", *PYTHON_SOURCE],
        [*ruff, "check", "--config", "pyproject.toml", *PYTHON_SOURCE],
        ["uv", "run", "--locked", "pyright"],
        ["uv", "run", "--locked", "pytest", "-q"],
        *(
            ["uv", "lock", "--check", "--script", name]
            for name in (*PYTHON_SOURCE[2:], "scripts/df.py", "scripts/install.py")
        ),
        ["uv", "lock", "--check", "--script", "scripts/sandbox.py"],
        ["uv", "run", "--locked", "--script", "scripts/sandbox.py", "--self-test"],
    ]
    for arguments in python_commands:
        status = run(arguments, env, SUPPORT)
        if status:
            return status
    commands = [
        [
            "node",
            "--test",
            ".dotfiles/tests/prompt.test.mjs",
            ".dotfiles/tests/deepen.test.mjs",
            ".dotfiles/tests/questions.test.mjs",
        ],
        [
            "node",
            "--no-warnings",
            "--input-type=module",
            "-e",
            TYPESCRIPT_CHECK,
            *TYPESCRIPT_SOURCE,
        ],
        ["node", "--check", ".config/shell-prompt/context.mjs"],
        ["node", "--check", ".config/shell-prompt/model.mjs"],
        ["shellcheck", "-S", "warning", *SHELL_SOURCE],
    ]
    commands.extend(["bash", "-n", name] for name in SHELL_SOURCE)
    commands.extend(
        ["zsh", "-n", str(path)]
        for path in [
            ROOT / ".zshrc",
            ROOT / ".zshenv",
            ROOT / ".zprofile",
            *sorted((ROOT / ".config/zsh/functions").iterdir()),
        ]
    )
    # Compile Lua without starting the editor configuration or its plugin installer.
    lua = "for _,p in ipairs(vim.fn.glob(vim.env.DOTFILES_SOURCE .. '/.config/nvim/**/*.lua', false, true)) do assert(loadfile(p)) end"
    for arguments in commands:
        status = run(arguments, env)
        if status:
            return status
    with tempfile.TemporaryDirectory(prefix="dotfiles-lua-") as directory:
        home = Path(directory)
        lua_env = {
            "PATH": env["PATH"],
            "HOME": directory,
            "DOTFILES_SOURCE": str(ROOT),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_STATE_HOME": str(home / ".local/state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
        }
        status = run(["nvim", "--clean", "--headless", "-c", "lua " + lua, "-c", "qa"], lua_env)
        if status:
            return status
    for directory in (ROOT / ".config", ROOT / ".pi"):
        for path in directory.rglob("*"):
            if path.suffix == ".json":
                _ = json.loads(path.read_bytes())
            elif path.suffix == ".toml":
                _ = tomllib.loads(path.read_text())
    status = run(
        ["uv", "run", "--locked", "zensical", "build", "--clean", "--strict"], env, SUPPORT
    )
    if status:
        return status
    git = ["git", "-C", str(ROOT)]
    if (ROOT / ".dotfiles.git").is_dir():
        git = ["git", f"--git-dir={ROOT / '.dotfiles.git'}", f"--work-tree={ROOT}"]
    status = run([*git, "diff", "--check"], env)
    if status:
        return status
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
