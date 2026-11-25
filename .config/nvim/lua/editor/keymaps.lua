local M = {}

local function pick_action(actions)
  require('mini.pick').ui_select(actions, {
    prompt = 'Actions · ↑↓ move · PgUp/PgDn page · Enter run',
    format_item = function(item)
      local shortcut = item.keys:gsub('<leader>', 'Space '):gsub('<CR>', '')
        :gsub('<C%-(.)>', 'Ctrl+%1'):gsub('<M%-(.)>', 'Alt+%1')
      return string.format('%-30s  %s', item.label, shortcut)
    end,
  }, function(item)
    if item then vim.api.nvim_feedkeys(vim.keycode(item.keys), 'mi', false) end
  end, {
    mappings = { scroll_down = '<PageDown>', scroll_up = '<PageUp>' },
    window = {
      prompt_prefix = 'Search actions › ',
      config = function()
        local width = math.min(76, math.floor(vim.o.columns * 0.9))
        local height = math.min(14, math.floor(vim.o.lines * 0.6))
        return {
          anchor = 'NW', width = width, height = height,
          col = math.floor((vim.o.columns - width) / 2), row = math.floor((vim.o.lines - height) / 2),
        }
      end,
    },
  })
end

function M.setup()
  local actions = {}
  local function map(mode, keys, action, description)
    vim.keymap.set(mode, keys, action, { silent = true, desc = description })
    if mode == 'n' then actions[#actions + 1] = { label = description, keys = keys } end
  end

  map('n', '<leader>f', function() require('fff').find_files() end, 'Find files')
  map('n', '<leader>1', '<cmd>25Lexplore<CR>', 'Toggle file sidebar')
  map('n', '<leader>2', function() require('editor.agent').toggle() end, 'Toggle AI agent pane')
  map('n', '<leader>/', function() require('fff').live_grep() end, 'Search file contents')
  vim.list_extend(actions, {
    { label = 'Save file', keys = ':write<CR>' },
    { label = 'Undo change', keys = 'u' },
    { label = 'Redo change', keys = '<C-r>' },
    { label = 'Enter an editor command', keys = ':' },
  })
  vim.keymap.set('n', '<leader>p', function() pick_action(actions) end, { desc = 'Search editor actions' })
  map('n', '<leader>?', function() require('which-key').show({ global = true }) end, 'Show keybindings')
  map('n', '<leader>cf', function() require('editor.lsp').format_current_buffer() end, 'Format current buffer')
  map('n', '<leader>ca', vim.lsp.buf.code_action, 'Code actions')
  map('n', '<leader>cr', vim.lsp.buf.rename, 'Rename symbol')
  map('n', '<leader>cd', vim.diagnostic.open_float, 'Show line diagnostics')
  map('n', '<leader>gd', vim.lsp.buf.definition, 'Go to definition')
  map('n', '<leader>gr', vim.lsp.buf.references, 'Find references')
  map('n', '<leader>gs', function() require('gitsigns').preview_hunk() end, 'Preview Git change')
  map('n', '<leader>gb', function() require('gitsigns').blame_line({ full = true }) end, 'Blame current line')
  map('n', '<leader>gD', function() require('gitsigns').diffthis() end, 'Diff against Git index')
  map('n', ']h', function() require('gitsigns').nav_hunk('next') end, 'Next Git change')
  map('n', '[h', function() require('gitsigns').nav_hunk('prev') end, 'Previous Git change')
  map('n', '<leader>hh', '<cmd>help<CR>', 'Neovim help')
  map('n', '<leader>ht', '<cmd>Tutor<CR>', 'Learn Neovim motions')
  map('n', '<leader>hc', '<cmd>checkhealth editor<CR>', 'Check editor dependencies')
  map('n', '<Esc>', '<cmd>nohlsearch<CR>', 'Clear search highlight')
  for _, move in ipairs({ { 'h', 'left' }, { 'j', 'down' }, { 'k', 'up' }, { 'l', 'right' } }) do
    local key, direction = unpack(move)
    map('n', '<C-' .. key .. '>', '<C-W>' .. key, 'Focus window ' .. direction)
    map('n', '<M-' .. key .. '>', '<C-W>' .. key:upper(), 'Move split ' .. direction)
  end
  map('i', '<C-Space>', vim.lsp.completion.get, 'Request LSP completion')
end

return M
