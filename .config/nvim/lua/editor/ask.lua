local M = {}
local api = vim.api

function M.show(buf)
  api.nvim_open_win(buf, true, { split = 'right', win = -1 })
  vim.wo.winbar = '%#Title# Ask AI %*· %{b:ask_provider}%=%{b:ask_status} '
  vim.wo.number = false
  vim.wo.relativenumber = false
  vim.wo.signcolumn = 'no'
  vim.wo.colorcolumn = ''
  vim.wo.cursorline = false
  vim.wo.wrap = true
  vim.wo.linebreak = true
end

function M.open(command)
  local buf = api.nvim_create_buf(false, true)
  local provider = vim.fs.basename(command)
  vim.b[buf].ask_provider = provider == 'ai-ask' and vim.env.AI_PROVIDER or provider
  vim.b[buf].ask_status = 'Enter send · Ctrl-J newline'
  vim.bo[buf].bufhidden = 'hide'
  vim.t.editor_ask = buf
  M.show(buf)

  local function submit()
    local lines = api.nvim_buf_get_lines(buf, 0, -1, false)
    local question = table.concat(lines, '\n')
    if vim.trim(question) == '' then return end
    vim.cmd.stopinsert()
    vim.keymap.del('i', '<CR>', { buffer = buf })
    vim.keymap.del('n', '<CR>', { buffer = buf })
    table.insert(lines, 1, '## Question')
    vim.list_extend(lines, { '', '## Answer', '' })
    api.nvim_buf_set_lines(buf, 0, -1, false, lines)
    vim.bo[buf].modifiable = false
    vim.b[buf].ask_status = 'Waiting for answer…'
    vim.treesitter.language.register('markdown', 'askmarkdown')
    vim.bo[buf].filetype = 'askmarkdown'
    vim.treesitter.start(buf, 'markdown')

    local function finish(result)
      if not api.nvim_buf_is_loaded(buf) then return end
      local output = (result.stdout or ''):gsub('\n$', '')
      local success = result.code == 0 and result.signal == 0 and vim.trim(output) ~= ''
      if not success then
        output = vim.trim(result.stderr or '')
        if output == '' then output = 'The backend returned no answer (exit ' .. result.code .. ').' end
      end
      vim.bo[buf].modifiable = true
      if not success then api.nvim_buf_set_lines(buf, #lines - 2, #lines - 1, false, { '## Request failed' }) end
      api.nvim_buf_set_lines(buf, -1, -1, false, vim.split(output, '\n', { plain = true }))
      vim.bo[buf].modifiable = false
      vim.b[buf].ask_status = success and 'q dismiss' or 'Request failed · q dismiss'
      vim.cmd.redrawstatus()
    end
    local started, process = pcall(vim.system, { command }, { stdin = question, text = true }, vim.schedule_wrap(finish))
    if not started then
      finish({ code = -1, stderr = tostring(process) })
      return
    end
    api.nvim_create_autocmd('BufWipeout', {
      buffer = buf, once = true,
      callback = function() if not process:is_closing() then process:kill('sigint') end end,
    })
  end

  vim.keymap.set({ 'i', 'n' }, '<CR>', submit, { buffer = buf, desc = 'Send question' })
  vim.keymap.set('i', '<Esc>', function()
    local draft = table.concat(api.nvim_buf_get_lines(buf, 0, -1, false), '\n')
    return vim.trim(draft) == '' and '<Esc><cmd>bwipeout<CR>' or '<Esc>'
  end, { buffer = buf, expr = true, desc = 'Leave draft or dismiss empty question' })
  vim.keymap.set('n', 'q', function() api.nvim_buf_delete(buf, { force = true }) end,
    { buffer = buf, desc = 'Dismiss question or answer' })
  vim.cmd.startinsert()
end

return M
