vim.o.background = 'dark'
vim.cmd('highlight clear')
vim.g.colors_name = 'neon-arcade'

-- ANSI slots match the Rex and Ghostty Neon Arcade palette.
local ansi = {
  '#1a1a28', '#ff5370', '#3ddc97', '#ffd166', '#4f9cff', '#c774ff', '#2fd6e0', '#b8bcd8',
  '#5c5e78', '#ff7a92', '#6ceeb4', '#ffe08a', '#7cb6ff', '#da9bff', '#63e6ee', '#f0f2ff',
}
for index, color in ipairs(ansi) do vim.g['terminal_color_' .. (index - 1)] = color end

local bg, fg, cursor, selection = '#0d0d15', '#d8dcf0', '#ff4fd8', '#2c2c4a'
local groups = {
  Normal = { fg = fg, bg = bg },
  NormalFloat = { fg = fg, bg = ansi[1] },
  FloatBorder = { fg = ansi[7], bg = ansi[1] },
  Cursor = { fg = bg, bg = cursor },
  CursorLine = { bg = ansi[1] },
  LineNr = { fg = ansi[9] },
  CursorLineNr = { fg = ansi[4], bold = true },
  ColorColumn = { bg = ansi[1] },
  WinSeparator = { fg = ansi[9] },
  Visual = { fg = ansi[16], bg = selection },
  Pmenu = { link = 'NormalFloat' },
  PmenuSel = { fg = bg, bg = ansi[7] },
  StatusLine = { fg = ansi[16], bg = selection },
  StatusLineNC = { fg = ansi[8], bg = ansi[1] },
  Search = { fg = bg, bg = ansi[4] },
  IncSearch = { fg = bg, bg = cursor },
  Comment = { fg = ansi[8], italic = true },
  Constant = { fg = ansi[4] },
  String = { fg = ansi[3] },
  Identifier = { fg = fg },
  Function = { fg = ansi[13] },
  Statement = { fg = ansi[6], bold = true },
  PreProc = { fg = ansi[14] },
  Type = { fg = ansi[7] },
  Special = { fg = ansi[10] },
  Directory = { fg = ansi[7], bold = true },
  DiagnosticError = { fg = ansi[2] },
  DiagnosticWarn = { fg = ansi[4] },
  DiagnosticInfo = { fg = ansi[5] },
  DiagnosticHint = { fg = ansi[7] },
  Added = { fg = ansi[3] },
  Changed = { fg = ansi[4] },
  Removed = { fg = ansi[2] },
}
for name, attributes in pairs(groups) do vim.api.nvim_set_hl(0, name, attributes) end
