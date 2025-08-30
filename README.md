# Dotfiles

> Hello, welcome $HOME
<img width="1512" height="982" alt="Screenshot 2025-08-30 at 13 09 35" src="https://github.com/user-attachments/assets/3c426922-275e-40d9-8904-8b402f4ce182" />


Personal dotfiles repository for macOS, managed with [Dotbot](https://github.com/anishathalye/dotbot).

## Quick Start

1. **Fresh machine setup**: Clone and bootstrap for complete setup
   ```bash
   git clone https://github.com/devadathanmb/mac-dotfiles.git ~/.dotfiles
   cd ~/.dotfiles
   ./bootstrap-mac.sh
   ```

2. **Symlink dotfiles**: After setup, symlink your configs
   ```bash
   # Dry run first
   ./install --dry-run

   # Once confirmed, run
   ./install
   ```

## License

See [LICENSE](LICENSE) for details.
