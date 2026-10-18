# Claude Code statusline

`statusline.sh` renders the two-line Claude Code footer. `settings.json` runs it
as `bash $HOME/.claude/statusline/statusline.sh`; this folder is symlinked to
`~/.claude/statusline` by `install.conf.yaml`. The design notes and layout rules
are in the header of `statusline.sh`.

## Previewing changes

Edit `statusline.sh`, then either:

- **Terminal:** `./preview [scenario...]` renders scenarios at several widths
  without launching Claude Code. It accepts these environment variables:
  - `WIDTHS="150 90"`: which column widths to render.
  - `STATUSLINE_BASH=/bin/bash`: which shell runs the script.
- **Live footer:** start a session with `STATUSLINE_DEV=1 claude`, then switch
  what it shows with `./use <scenario>` (or `!~/.claude/statusline/use crit`
  from inside that session). `./use off` restores the real payload and `./use`
  lists the scenarios. Sessions started without `STATUSLINE_DEV` are never
  affected.

Scenarios are JSON payload fragments deep-merged over `scenarios/_base.json`.
Strings like `"+3600"` become `now + 3600`, so reset and expiry times stay
relative. Add a scenario by adding a file.

| Scenario | Shows |
|---|---|
| `calm` | fresh session, everything on pace |
| `busy` | high effort, warm cache, cost, lines changed, approved PR |
| `warn` | context 67%, 5h limit ahead of pace, cold cache with miss cause, changes requested |
| `crit` | context 88%, 5h limit 91%, max effort, fast mode, worktree, agent |
| `api` | no subscription limits, 200k window, vim mode |

## Before committing

- Every glyph must be single-width. Widths are counted in characters, so a
  wide glyph (emoji such as ⚡) overflows the line and Claude Code truncates
  the right column.
- The script must behave identically under macOS `/bin/bash` 3.2 (no `\u`
  escapes, no associative arrays):

  ```sh
  export STATUSLINE_NOW=$(date +%s) WIDTHS="200 120 80 70"
  diff <(./preview) <(STATUSLINE_BASH=/bin/bash ./preview) && echo parity ok
  ```

- `shellcheck -s bash statusline.sh use preview`
