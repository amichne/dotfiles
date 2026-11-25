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
    if vim.b[buf].editor_ask or vim.fn.jobwait({ vim.b[buf].terminal_job_id }, 0)[1] == -1 then
      vim.cmd('botright vsplit')
      vim.api.nvim_win_set_buf(0, buf)
      if not vim.b[buf].editor_ask then vim.cmd.startinsert() end
      return
    end
    vim.api.nvim_buf_delete(buf, { force = true })
  end

  local agent = vim.env.NVIM_AGENT or 'codex'
  if vim.fn.executable(agent) ~= 1 then
    vim.notify('Agent executable missing: ' .. agent .. '. Set NVIM_AGENT to its path or name.', vim.log.levels.ERROR)
    return
  end
  local command = { agent }
  local ask = vim.fs.basename(agent) == 'ai-ask'
  if ask then
    local question = vim.fn.input('Ask AI: ')
    if vim.trim(question) == '' then return end
    command = { agent, '--', question }
  end
  vim.cmd('botright vnew')
  buf = vim.api.nvim_get_current_buf()
  if vim.fn.jobstart(command, { term = true }) <= 0 then
    vim.api.nvim_buf_delete(buf, { force = true })
    vim.notify('Could not start agent: ' .. agent, vim.log.levels.ERROR)
    return
  end
  vim.t.editor_agent = buf
  vim.bo[buf].bufhidden = 'hide'
  if ask then
    vim.b[buf].editor_ask = true
    vim.keymap.set('n', 'q', '<cmd>bwipeout<CR>', { buffer = buf, desc = 'Dismiss AI answer' })
  else
    vim.cmd.startinsert()
  end
end

return M
