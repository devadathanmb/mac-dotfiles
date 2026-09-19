vim.opt.clipboard = "unnamedplus"
vim.opt.expandtab = true
vim.opt.ignorecase = true
vim.opt.iskeyword:append("-")
vim.opt.number = true
vim.opt.numberwidth = 4
vim.opt.relativenumber = false
vim.opt.shiftwidth = 2
vim.opt.smartcase = true
vim.opt.smartindent = true
vim.opt.splitbelow = true
vim.opt.splitright = true
vim.opt.tabstop = 2
vim.opt.termguicolors = true
vim.opt.cursorline = true
vim.opt.wrap = false
vim.g.mapleader = " "

vim.api.nvim_create_autocmd("TextYankPost", {
	callback = function()
		vim.highlight.on_yank({ higroup = "IncSearch", timeout = 200 })
	end,
})

local function toggle_netrw()
	if vim.bo.filetype == "netrw" then
		vim.cmd("Lexplore!")
	else
		vim.cmd("Lexplore")
	end
end

vim.keymap.set("n", "<leader>e", toggle_netrw, { silent = true })
