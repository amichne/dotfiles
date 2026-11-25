local M = {}

-- Each tab keeps its own job when its terminal window is hidden.
function M.toggle()
  local buf = vim.t.editor_agent
  if buf and vim.api.nvim_buf_is_valid(buf) then
    local win = vim.fn.bufwinid(buf)
    if win ~= -1 then
      if #vim.api.nvim_tabpage_list_wins(0) == 1 then vim.cmd.enew()
      else vim.api.nvim_win_hide(win) end
      return
    end
    if vim.fn.jobwait({ vim.b[buf].terminal_job_id }, 0)[1] == -1 then
      vim.cmd('botright vsplit')
      vim.api.nvim_win_set_buf(0, buf)
      vim.cmd.startinsert()
      return
    end
    vim.api.nvim_buf_delete(buf, { force = true })
  end

  local agent = vim.env.NVIM_AGENT or 'codex'
  if vim.fn.executable(agent) ~= 1 then
    vim.notify('Agent executable missing: ' .. agent .. '. Set NVIM_AGENT to its path or name.', vim.log.levels.ERROR)
    return
  end
  vim.cmd('botright vnew')
  buf = vim.api.nvim_get_current_buf()
  if vim.fn.jobstart({ agent }, { term = true }) <= 0 then
    vim.api.nvim_buf_delete(buf, { force = true })
    vim.notify('Could not start agent: ' .. agent, vim.log.levels.ERROR)
    return
  end
  vim.t.editor_agent = buf
  vim.bo[buf].bufhidden = 'hide'
  vim.cmd.startinsert()
end

return M
