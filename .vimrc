" Use UTF-8 encoding
set encoding=utf-8
set fileencoding=utf-8

" Line numbers
set number
set relativenumber

" Indentation
set tabstop=4       " Number of spaces that a <Tab> counts for
set shiftwidth=4    " Number of spaces for each indent
set expandtab       " Use spaces instead of tabs
set smartindent     " Automatically indent new lines

" Searching
set ignorecase      " Case-insensitive search…
set smartcase       " …unless uppercase used
set incsearch       " Show matches as you type
set hlsearch        " Highlight matches

" UI
set cursorline      " Highlight current line
set showmatch       " Highlight matching brackets
syntax on           " Enable syntax highlighting
set termguicolors   " True color support

" Better splits
set splitbelow
set splitright

" Clipboard (use system clipboard)
set clipboard=unnamedplus

" Faster updates
set updatetime=300

" Mappings
nnoremap <SPACE> <Nop>          " Map leader key to space
let mapleader=" "

nnoremap <leader>w :w<CR>       " Quick save
nnoremap <leader>q :q<CR>       " Quick quit
nnoremap <leader>h :nohlsearch<CR> " Clear search highlight