-- Keep the editor useful while dependency failures remain visible in :checkhealth editor.
-- A layered install links this file into XDG_CONFIG_HOME. Load its sibling modules.
local init = vim.fn.resolve(debug.getinfo(1, 'S').source:sub(2))
local root = vim.fs.dirname(init)
if root ~= vim.fn.stdpath('config') then vim.opt.rtp:prepend(root) end
require('editor.options').setup()
vim.cmd.colorscheme('neon-arcade')
require('editor.keymaps').setup()
require('editor.lsp').setup()

local result = require('editor.plugins').setup()
if result.outcome ~= 'READY' then
  vim.schedule(function()
    vim.notify('Editor plugins: ' .. result.outcome .. ' at ' .. result.stage ..
      '. Run :checkhealth editor for the required dependency or pin.', vim.log.levels.ERROR)
  end)
end
