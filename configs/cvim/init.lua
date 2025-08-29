-- Set line numbers
vim.opt.number = true

-- Use the system clipboard
vim.opt.clipboard = "unnamedplus"

-- Highlight text on yank
vim.api.nvim_create_autocmd('TextYankPost', {
    callback = function()
        vim.highlight.on_yank { higroup = 'IncSearch', timeout = 200 }
    end,
})

vim.opt.ignorecase = true -- Ignore case while searching
vim.opt.smartcase = true -- Smart case searching

-- Indentation and line wrap
vim.opt.smartindent = true -- Make indentation smarter
vim.opt.wrap = false -- No line wrapping
vim.opt.expandtab = true -- Expand tab to spaces
vim.opt.tabstop = 2 -- 4 spaces for a tab
vim.opt.shiftwidth = 2 -- 4 spaces for each indentation

-- Line numbering : Hybrid numbering
vim.opt.number = true
vim.opt.relativenumber = false
vim.opt.numberwidth = 4 -- Sets number col width to 2

-- Cursor line
vim.opt.cursorline = true -- Highlight the current line

-- Split options
vim.opt.splitbelow = true -- Force horizontal splits below
vim.opt.splitright = true -- Force vertical splits to right

-- Terminal gui colors to support more colors
vim.opt.termguicolors = true

-- Consider string-string as whole word
vim.opt.iskeyword:append("-")

-- Set the leader key to space
vim.g.mapleader = " "

-- Function to toggle netrw
function ToggleNetrw()
    local bufname = vim.fn.bufname()
    if bufname == "" or vim.bo.filetype ~= "netrw" then
        vim.cmd("Lexplore")
    else
        vim.cmd("Lexplore!")
    end
end

-- Map <Leader>e to toggle netrw
vim.api.nvim_set_keymap("n", "<leader>e", ":lua ToggleNetrw()<CR>", { noremap = true, silent = true })
