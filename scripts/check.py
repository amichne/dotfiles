from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SOURCE = ("scripts", "tests", ".local/bin/keys")
SHELL_SOURCE = (
    "bin/ai",
    "bin/dotfiles",
    ".local/bin/df",
    ".local/bin/dotfiles",
    ".local/bin/shell-prompt",
    "scripts/check.sh",
    "ai/tasks/ci",
    "ai/tasks/review",
)


def run(arguments: list[str], env: dict[str, str]) -> int:
    print("==> " + " ".join(arguments), flush=True)
    return subprocess.run(arguments, cwd=ROOT, env=env, check=False).returncode


def main() -> int:
    for name in ("uv", "node", "zsh", "shellcheck", "mise", "git", "nvim"):
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
    commands = [
        ["uv", "run", "--locked", "ruff", "format", "--check", *PYTHON_SOURCE],
        ["uv", "run", "--locked", "ruff", "check", *PYTHON_SOURCE],
        ["uv", "run", "--locked", "pyright"],
        ["uv", "run", "--locked", "pytest", "-q"],
        ["uv", "lock", "--check", "--script", ".local/bin/keys"],
        ["uv", "lock", "--check", "--script", "scripts/df.py"],
        ["node", "--test", "tests/prompt.test.mjs"],
        ["node", "--check", ".config/shell-prompt/context.mjs"],
        ["node", "--check", ".config/shell-prompt/model.mjs"],
        ["uv", "run", "--locked", "--project", "ai", "python", "ai/check.py"],
        ["shellcheck", "-S", "warning", *SHELL_SOURCE],
    ]
    commands.extend(["bash", "-n", name] for name in SHELL_SOURCE)
    commands.extend(
        ["zsh", "-n", str(path)]
        for path in [
            ROOT / ".zshrc",
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
    status = run(["uv", "run", "--locked", "zensical", "build", "--clean", "--strict"], env)
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
