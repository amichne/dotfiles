from __future__ import annotations

import shutil

import pytest

from .conftest import Home


def test_ai_ask_keeps_a_completed_answer_until_dismissed(home: Home) -> None:
    nvim = shutil.which("nvim")
    assert nvim is not None
    version = home.run(nvim, "--clean", "--headless", "+lua print(vim.fn.has('nvim-0.12'))", "+qa")
    if version.stderr.strip() == "0":
        pytest.skip("the editor configuration needs Neovim 0.12 or later")
    assert version.returncode == 0 and version.stderr.strip() == "1", version.stderr

    ask = home.tools / "ai-ask"
    _ = ask.write_text('#!/bin/sh\n[ "$#" -eq 2 ] && [ "$1" = -- ] || exit 64\nprintf "%s" "$2"\n')
    ask.chmod(0o755)
    home.env["NVIM_AGENT"] = str(ask)
    probe = home.path / "probe.lua"
    _ = probe.write_text("""
vim.opt.rtp:prepend(vim.fn.stdpath('config'))
vim.g.mapleader = ' '
require('editor.keymaps').setup()
local function press(keys)
  vim.api.nvim_feedkeys(vim.keycode(keys), 'mx', false)
end
local function run()
  press(' 2<Esc>')
  assert(#vim.api.nvim_list_wins() == 1)
  local question = '--literal $(id)'
  press(' 2' .. question .. '<CR>')
  local buf = vim.api.nvim_get_current_buf()
  assert(vim.bo[buf].buftype == 'terminal')
  press(' 2')
  assert(vim.fn.bufwinid(buf) == -1)
  assert(vim.wait(3000, function()
    return vim.fn.jobwait({vim.b[buf].terminal_job_id}, 0)[1] ~= -1
      and vim.api.nvim_buf_get_lines(buf, 0, 1, false)[1] == question
  end))
  press(' 2')
  assert(vim.api.nvim_get_current_buf() == buf)
  press('q')
  assert(not vim.api.nvim_buf_is_valid(buf))
end
local ok, err = xpcall(run, debug.traceback)
if not ok then print(err) end
vim.cmd(ok and 'qa!' or 'cq! 1')
""")
    result = home.run(nvim, "--clean", "--headless", "-c", "luafile probe.lua")
    assert result.returncode == 0, result.stderr
