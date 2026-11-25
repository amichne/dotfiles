local M = {}

-- Hide only the pinned agentic welcome block. The transcript still contains its metadata.
local chat_meta = vim.api.nvim_create_namespace('editor_acp_session_details')
local function hide_chat_details(buf)
  if not vim.api.nvim_buf_is_loaded(buf) then return end
  local lines = vim.api.nvim_buf_get_lines(buf, 0, 4, false)
  if #lines == 4 and lines[1]:match('^# Agentic %- ') and lines[2]:match('^%- session id: ')
      and lines[3]:match('^%- %d%d%d%d%-') and lines[4] == '--- --' then
    vim.api.nvim_buf_set_extmark(buf, chat_meta, 0, 0, {
      id = 1, end_row = 3, end_col = #lines[4], conceal_lines = '', invalidate = true,
    })
  else
    vim.api.nvim_buf_del_extmark(buf, chat_meta, 1)
  end
end

M.lazy_commit = '306a05526ada86a7b30af95c5cc81ffba93fef97'
M.spec = {
  {
    'carlos-algms/agentic.nvim', commit = '4750d6ce4298b3018dd67f975a1457afbeeaa09f',
    lazy = true, main = 'agentic',
    opts = {
      provider = 'copilot-acp', provider_switcher = { hide_unhealthy_providers = true },
      headers = {
        chat = function(_, session)
          local provider = session and session:get_provider_name()
          return provider and ('Chat  /  ' .. provider:gsub(' ACP$', '')) or 'Chat'
        end,
        input = function() return 'Prompt  /  Ctrl-S sends' end,
        code = { title = 'Code' }, files = { title = 'Files' },
        diagnostics = { title = 'Diagnostics' }, todos = { title = 'Tasks' },
      },
      windows = {
        chat = { win_opts = { statusline = ' ' } },
        input = { height = 6, win_opts = { statusline = ' ', winhighlight = 'Normal:NeonPrompt,EndOfBuffer:NeonPrompt' } },
      },
      chat_icons = { user = '', agent = '' },
      status_icons = { pending = '...', in_progress = '>', completed = '+', failed = '!' },
      permission_icons = { allow_once = '+', allow_always = '++', reject_once = '-', reject_always = '--' },
      message_icons = { thinking = 'Thinking', finished = 'Done', stopped = 'Stopped', error = 'Error' },
    },
  },
  {
    'MeanderingProgrammer/render-markdown.nvim', commit = '640a3ec6d538bad17c328be373c7cad0293d9589', -- v8.14.0
    ft = { 'askmarkdown', 'AgenticChat' }, main = 'render-markdown',
    opts = {
      file_types = { 'askmarkdown', 'AgenticChat' },
      sign = { enabled = false }, anti_conceal = { enabled = false },
      heading = { icons = { '▌ ', '▎ ', '› ' } },
      code = { language_icon = false },
      checkbox = { unchecked = { icon = '[ ] ' }, checked = { icon = '[x] ' }, custom = { todo = { rendered = '[-] ' } } },
      link = { enabled = false },
      overrides = { filetype = { AgenticChat = {
        render_modes = true,
        win_options = { concealcursor = { rendered = 'nvic' } },
      } } },
      on = { attach = function(ctx)
        if vim.bo[ctx.buf].filetype ~= 'AgenticChat' then return end
        hide_chat_details(ctx.buf)
        vim.api.nvim_buf_attach(ctx.buf, false, { on_lines = function(_, buf, _, first)
          if first < 4 then vim.schedule(function() hide_chat_details(buf) end) end
        end })
      end },
    },
  },
  {
    'nvim-mini/mini.pick', commit = '8c1f75f8ddd8c9f75d07ed2ab5718d2c3cb65a66', -- v0.18.0
    lazy = true,
    config = function()
      -- The palette uses MiniPick directly. Keep the current chooser for other plugins.
      local select = vim.ui.select
      require('mini.pick').setup()
      vim.ui.select = select
    end,
  },
  {
    'dmtrKovalenko/fff', commit = '95fd777c2529fc7b4d7572dabff64cc07268f2c5', -- v0.11.0
    lazy = false,
    build = function() require('fff.download').download_or_build_binary() end,
    opts = { debug = { enabled = false, show_scores = false } },
  },
  {
    'folke/which-key.nvim', commit = '3aab2147e74890957785941f0c1ad87d0a44c15a', lazy = false,
    opts = {
      preset = 'modern', delay = 250,
      icons = {
        mappings = false,
        keys = {
          Up = 'Up', Down = 'Down', Left = 'Left', Right = 'Right',
          C = 'Ctrl-', M = 'Alt-', D = 'Cmd-', S = 'Shift-',
          CR = 'Enter', Esc = 'Esc', NL = 'Enter', BS = 'Backspace',
          Space = 'Space ', Tab = 'Tab',
          ScrollWheelDown = 'ScrollDown', ScrollWheelUp = 'ScrollUp',
          F1 = 'F1', F2 = 'F2', F3 = 'F3', F4 = 'F4', F5 = 'F5', F6 = 'F6',
          F7 = 'F7', F8 = 'F8', F9 = 'F9', F10 = 'F10', F11 = 'F11', F12 = 'F12',
        },
      },
      spec = {
        { '<leader>c', group = 'Code' },
        { '<leader>g', group = 'Git and navigation' }, { '<leader>h', group = 'Help' },
      },
    },
  },
  {
    'lewis6991/gitsigns.nvim', commit = '070a5d7b985546cc57e1fc61e5bc507fecac6045',
    event = { 'BufReadPre', 'BufNewFile' }, opts = {},
  },
}

---@alias EditorBootstrapOutcome 'READY'|'MISSING_GIT'|'CLONE_FAILED'|'CHECKOUT_FAILED'|'PIN_UNVERIFIED'|'PIN_MISMATCH'
---@class EditorBootstrapResult
---@field outcome EditorBootstrapOutcome
---@field stage 'PREFLIGHT'|'CLONE'|'CHECKOUT'|'VERIFY'|'SETUP'
---@return EditorBootstrapResult
function M.setup()
  local path = vim.fn.stdpath('data') .. '/lazy/lazy.nvim'
  if vim.fn.executable('git') ~= 1 then return { outcome = 'MISSING_GIT', stage = 'PREFLIGHT' } end
  if not vim.uv.fs_stat(path) then
    local clone = vim.system({ 'git', 'clone', '--filter=blob:none',
      'https://github.com/folke/lazy.nvim.git', path }, { text = true }):wait(30000)
    if clone.code ~= 0 then return { outcome = 'CLONE_FAILED', stage = 'CLONE' } end
    local checkout = vim.system({ 'git', '-C', path, 'checkout', '--detach', M.lazy_commit }, { text = true }):wait(10000)
    if checkout.code ~= 0 then return { outcome = 'CHECKOUT_FAILED', stage = 'CHECKOUT' } end
  end
  local head = vim.system({ 'git', '-C', path, 'rev-parse', 'HEAD' }, { text = true }):wait(10000)
  if head.code ~= 0 then return { outcome = 'PIN_UNVERIFIED', stage = 'VERIFY' } end
  if vim.trim(head.stdout) ~= M.lazy_commit then return { outcome = 'PIN_MISMATCH', stage = 'VERIFY' } end
  vim.opt.rtp:prepend(path)
  require('lazy').setup(M.spec, {
    performance = { rtp = { reset = false } },
    lockfile = vim.fn.stdpath('state') .. '/lazy-lock.json',
    checker = { enabled = false }, change_detection = { notify = false },
  })
  return { outcome = 'READY', stage = 'SETUP' }
end

return M
