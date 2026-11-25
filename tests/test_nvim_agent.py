from __future__ import annotations

import shutil

import pytest

from .conftest import Home


@pytest.mark.parametrize("custom", [False, True])
def test_ai_ask_keeps_a_completed_answer_until_dismissed(home: Home, custom: bool) -> None:
    nvim = shutil.which("nvim")
    assert nvim is not None
    version = home.run(nvim, "--clean", "--headless", "+lua print(vim.fn.has('nvim-0.12'))", "+qa")
    if version.stderr.strip() == "0":
        pytest.skip("the editor configuration needs Neovim 0.12 or later")
    assert version.returncode == 0 and version.stderr.strip() == "1", version.stderr

    ask = home.tools / ("custom backend" if custom else "ai-ask")
    _ = ask.write_text(
        '#!/bin/sh\n[ "$#" -eq 0 ] || exit 64\nquestion=$(cat)\n'
        'if [ "$question" = fail ]; then echo "provider unavailable" >&2; exit 1; fi\n'
        'printf "%s\\n" "$question"\n'
    )
    ask.chmod(0o755)
    home.env["NVIM_ASK_COMMAND" if custom else "NVIM_AGENT"] = str(ask)
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
  press(' 2')
  local buf = vim.api.nvim_get_current_buf()
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, {question, '- second line'})
  press('<CR>')
  assert(vim.bo[buf].filetype == 'askmarkdown')
  press(' 2')
  assert(vim.fn.bufwinid(buf) == -1)
  assert(vim.wait(3000, function()
    return vim.b[buf].ask_status == 'q dismiss'
  end))
  local answer = vim.api.nvim_buf_get_lines(buf, -3, -1, false)
  assert(vim.deep_equal(answer, {question, '- second line'}), vim.inspect(answer))
  press(' 2')
  assert(vim.api.nvim_get_current_buf() == buf)
  press('q')
  assert(not vim.api.nvim_buf_is_valid(buf))
  press(' 2')
  vim.api.nvim_buf_set_lines(0, 0, -1, false, {'fail'})
  press('<CR>')
  assert(vim.wait(3000, function() return vim.b.ask_status == 'Request failed · q dismiss' end))
  assert(vim.fn.index(vim.fn.getline(1, '$'), '## Request failed') >= 0)
  assert(vim.fn.getline('$') == 'provider unavailable')
end
local ok, err = xpcall(run, debug.traceback)
if not ok then print(err) end
vim.cmd(ok and 'qa!' or 'cq! 1')
""")
    result = home.run(nvim, "--clean", "--headless", "-c", "luafile probe.lua")
    assert result.returncode == 0, result.stderr
