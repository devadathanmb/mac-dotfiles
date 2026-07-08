# mac-dots

> Hello, welcome $HOME

Personal macOS dotfiles and workstation provisioning.

This repository uses Ansible for setup and Dotbot for symlinks. It is built for my own machines first, but kept readable so others can inspect, borrow, or adapt what is useful.

## Table of Contents

- [Overview](#overview)
- [Install](#install)
- [Commands](#commands)
- [Layout](#layout)
- [License](#license)

## Overview

At a high level, this repo manages:

- Homebrew packages and applications
- macOS defaults
- shell, terminal, editor, and Git configuration
- symlinks from this repo into `$HOME`

The `Makefile` is the main entry point. Ansible playbooks live in `ansible/`, and Dotbot links are defined in `install.conf.yaml`.

## Install

> [!WARNING]
> This is a personal macOS setup. Review the repository before running it on your system. Setup commands change the live macOS environment, and Dotbot may replace existing files with symlinks.

```bash
git clone --recursive https://github.com/devadathanmb/mac-dotfiles.git ~/.mac-dots
cd ~/.mac-dots
make bootstrap
```

If the repo was cloned without submodules:

```bash
git submodule update --init --recursive
```

## Commands

```bash
make             # list available targets
make bootstrap   # first-time setup
make all         # run the full setup
make packages    # install packages and applications
make macos       # apply macOS defaults
make dotfiles    # link dotfiles
```

Pass Ansible flags through `ARGS` when needed:

```bash
make macos ARGS="--check --diff"
```

## Layout

```text
Makefile             command entry point
ansible/             playbooks, roles, inventory, and validation scripts
configs/             application configuration linked into $HOME
homebrew/            tracked Homebrew package lists
scripts/             helper scripts linked into ~/.local/bin
install.conf.yaml    Dotbot symlink map
dotbot/              Dotbot submodule
```

## License

[GPL 3.0](./LICENSE)
