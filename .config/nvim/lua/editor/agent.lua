local M = {}

local function toggle_existing(buf)
  if buf and vim.api.nvim_buf_is_valid(buf) then
    local win = vim.fn.bufwinid(buf)
    if win ~= -1 then
      if #vim.api.nvim_tabpage_list_wins(0) == 1 then vim.cmd.enew()
      else vim.api.nvim_win_hide(win) end
      return true
    end
    if vim.b[buf].ask_status then
      require('editor.ask').show(buf)
      return true
    end
    if vim.fn.jobwait({ vim.b[buf].terminal_job_id }, 0)[1] == -1 then
      vim.cmd('botright vsplit')
      vim.api.nvim_win_set_buf(0, buf)
      vim.cmd.startinsert()
      return true
    end
    vim.api.nvim_buf_delete(buf, { force = true })
  end
  return false
end

function M.ask()
  if toggle_existing(vim.t.editor_ask) then return end
  local legacy = vim.env.NVIM_AGENT
  local command = vim.env.NVIM_ASK_COMMAND or (legacy and vim.fs.basename(legacy) == 'ai' and legacy) or 'ai'
  if vim.fn.executable(command) ~= 1 then
    vim.notify('Ask AI executable missing: ' .. command, vim.log.levels.ERROR)
    return
  end
  require('editor.ask').open(command)
end

function M.terminal()
  if toggle_existing(vim.t.editor_terminal) then return end
  local agent = vim.env.NVIM_AGENT or 'codex'
  if vim.fs.basename(agent) == 'ai' then agent = 'codex' end
  if vim.fn.executable(agent) ~= 1 then
    vim.notify('Agent executable missing: ' .. agent, vim.log.levels.ERROR)
    return
  end
  vim.cmd('botright vnew')
  local buf = vim.api.nvim_get_current_buf()
  if vim.fn.jobstart({ agent }, { term = true }) <= 0 then
    vim.api.nvim_buf_delete(buf, { force = true })
    vim.notify('Could not start agent: ' .. agent, vim.log.levels.ERROR)
    return
  end
  vim.t.editor_terminal = buf
  vim.bo[buf].bufhidden = 'hide'
  vim.cmd.startinsert()
end

return M
