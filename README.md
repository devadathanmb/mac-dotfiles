# mac-dots

> Hello, welcome $HOME

Personal macOS setup using Ansible and Dotbot.

## Fresh Install

> [!WARNING]
> This setup changes macOS settings and links files from this repository into `$HOME`. Review it before running on another Mac.

1. Install Apple's Command Line Tools:

   ```bash
   xcode-select --install
   ```

   Wait for the installation to finish.

2. Clone and bootstrap:

   ```bash
   git clone --recursive https://github.com/devadathanmb/mac-dotfiles.git ~/.mac-dots
   cd ~/.mac-dots
   make bootstrap
   ```

The bootstrap requests the administrator password and installs the managed applications, packages, runtimes, dotfiles, and macOS settings.

Application exports in [`exports/`](./exports/) require manual import after setup.

## Commands

```bash
make bootstrap   # provision a fresh Mac
make all         # reapply the complete setup
make packages    # install managed packages and applications
make macos       # apply macOS settings
make dotfiles    # link managed configuration into $HOME
make backup      # refresh tracked package lists and backups
make hooks-run   # validate the repository
```

Preview Ansible changes without applying them:

```bash
make macos ARGS="--check --diff"
```

> [!CAUTION]
> `make backup` rewrites tracked package lists and backups from the current machine. Always review `git diff` afterward.

## License

[GPL 3.0](./LICENSE)
