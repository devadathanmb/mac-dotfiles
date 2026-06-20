# Damage Control

A tool-call firewall for the [pi coding agent](https://github.com/earendil-works/pi-coding-agent).

Damage Control intercepts every `tool_call` the agent makes — `bash`, `read`,
`write`, `edit`, `grep`, etc. — evaluates it against a set of YAML rules under a
**mode**, and then **allows**, **asks**, or **blocks** it. When a call is blocked the
agent is told *why* and instructed not to retry or work around it, so it adapts
instead of fighting the wall.

```
 Damage Control  ·  needs your permission

  tool bash  ·  rule git.force-push  ·  op execute  ·  mode ask

  ▌ Force push to remote

  Command
    git push --force origin main

  → Allow once               Run this exact tool call now
    Allow for session         Don't ask again for this exact invocation
    Allow rule for session    Don't ask again for the "git.force-push" rule this session
    Deny                      Block it and tell the agent to adapt

  ↑↓ navigate  ·  ⏎ confirm  ·  esc deny
```

---

## Install

Drop the extension where pi auto-discovers extensions (a `*.ts` file or a
`subdir/index.ts`), then create a config file (see [Configuration](#configuration)).
Copy [`damage-control.example.yaml`](./damage-control.example.yaml) to your global
config path to get started:

```sh
cp damage-control.example.yaml ~/.pi/agent/damage-control.yaml
```

---

## Modes

The mode decides what happens to a tool call that **no rule matches**. Matched rules
always apply regardless of mode (a `block` rule blocks even in `blacklist`).

| Mode | Unmatched call | Use it when… |
|------|----------------|--------------|
| `off` | allow | You want the firewall disabled entirely. |
| `yolo` | allow | You're temporarily okay with everything (a transient override; restores the previous mode when toggled off). |
| `blacklist` | **allow** | Default. Run freely; only the dangerous things you've listed are gated. |
| `whitelist` | **block** (read-only ops still allowed) | Lock down to an explicit allow-list. Pure `read`/`list` operations pass so the agent can still navigate. |
| `ask` | **ask** | Approve every non-trivial call by hand. |

> **Whitelist tip:** a whitelist with only `ask`/`block` rules blocks all writes and
> bash. Add `allow` rules for the operations you trust. The extension warns on startup
> if whitelist mode is active with no `allow` rules.

### Decision precedence

When several rules match one call, **the most restrictive action wins**
(`block` > `ask` > `allow`). On a tie, the **first** matching rule (top-to-bottom in
YAML) provides the reason, so reordering rules never changes behavior silently.

When a call needs approval you get up to four choices:

- **Allow once** — run this exact call now.
- **Allow for session** — don't ask again for this *exact* invocation.
- **Allow rule for session** — don't ask again for the *matched rule* this session, even
  if the command differs slightly (an added flag, a different path). Only shown when a
  rule matched. `block` rules are never session-allowed.
- **Deny** — block it and tell the agent to adapt.

Both session scopes are cleared when a new session starts.

---

## Configuration

### File locations

| Scope | Path | Loaded |
|-------|------|--------|
| Global | `~/.pi/agent/damage-control.yaml` | Always. |
| Project | `<cwd>/.pi/damage-control.yaml` | If present, **merged on top** of global. |

Merge semantics: `mode` overrides; the `keymaps`/`ui`/`feedback` objects shallow-merge;
**`rules` are concatenated** (project rules are appended); `disableRules` ids are
removed from the merged set last. So a project can *add* rules and *drop* specific
global rules by id, but can't edit a global rule in place.

### Top-level keys

```yaml
mode: blacklist                  # off | yolo | blacklist | whitelist | ask

cycleModes:                      # order the cycle shortcut steps through
  - blacklist
  - whitelist
  - ask
  - yolo

keymaps:
  cycleMode: shift+tab           # cycle through cycleModes
  toggleYolo: ctrl+shift+y       # jump to YOLO and back

ui:
  footerStatus: true             # show "DC <mode>" in the footer
  notifyOnBlock: true            # toast when a call is blocked
  notifyOnAsk: false             # toast when a call needs approval
  showChatMessages: true         # render block decisions inline in the transcript

feedback:
  blockedToolResult: continue    # continue = tell the agent and keep going; abort = stop the turn
  includeAdaptationHints: true   # add "if destructive, stop and ask" guidance to the agent

disableRules: []                 # ids of (usually global) rules to drop

rules: []                        # see below
```

> **No UI?** In headless modes (`-p` / JSON) there's nothing to prompt, so an `ask`
> decision is **blocked** and the agent is told why. Damage Control assumes you run it
> interactively.

---

## Rules

Each rule has an `id`, a human `description` (shown as the reason), a `match`, and an
`action`. `feedback.agentHint` is optional.

```yaml
- id: git.force-push             # unique; also the handle for disableRules
  description: Force push to remote
  action: ask                    # allow | ask | block
  match:
    tool: bash
    command:
      program: git
      argsSequence: ["push"]
      flagsAny: ["--force", "--force-with-lease", "-f"]
  feedback:
    agentHint: Ask the user before force-pushing.   # extra line shown to the agent on block
```

### `match` fields

A rule matches only if **every** field present in `match` matches (logical AND).

| Field | Matches when |
|-------|--------------|
| `tool` | The tool name equals this (e.g. `bash`, `read`, `write`, `edit`, `grep`). |
| `toolsAny` | The tool name is in this list. |
| `commandRegex` | The raw `bash` command string matches this JS regex. Invalid regexes are reported at load time, never silently ignored. |
| `command` | The parsed `bash` command matches the [`command` sub-fields](#command-sub-fields). |
| `path` | A path touched by the call matches the [`path` sub-fields](#path-sub-fields). |

#### `command` sub-fields

The command string is tokenized (quotes/escapes handled) before matching.

| Field | Matches when |
|-------|--------------|
| `program` | The first token (the program) equals this. |
| `startsWith` | The trimmed command starts with this string. |
| `includesAny` | The command contains any of these substrings. |
| `argsSequence` | These tokens appear consecutively, in order (e.g. `["reset", "--hard"]`). |
| `flagsAny` | Any of these flags is present. Short flags match inside bundles (`-rf` matches `-f`). |
| `flagsAll` | All of these flags are present. |

#### `path` sub-fields

| Field | Matches when |
|-------|--------------|
| `globAny` | Any touched path matches one of these globs. |
| `except` | …but **not** if it also matches one of these globs (carve-outs). |
| `operationsAny` | Restrict to certain operations (`read`, `list`, `write`, `edit`, `delete`, `move`, `execute`). Omit to match any. |

**Globs** support `*` (within a path segment) and `**` (across segments) only. `~`
expands to your home directory. `?`, `[...]`, and `{a,b}` are **not** supported — they
match literally, and the extension warns at load time if a glob uses them.

**Operations** are inferred per tool: `read` → `read`; `grep`/`find`/`ls` →
`read`+`list`; `write` → `write`; `edit` → `edit`+`write`; `bash` → `execute`, plus
`delete`/`move`/`write`/`edit` when it spots `rm`/`mv`/redirects/`sed -i`, and `read`
for known readers (`cat`, `less`, `head`, `tail`, `bat`, …). Because bash is always
`execute`, a path rule scoped to `operationsAny: ["read"]` only catches a bash reader
if you don't also require `execute`.

---

## Commands

| Command | Action |
|---------|--------|
| `/dc` or `/dc status` | Show current mode, rule count, and keymaps. |
| `/dc reload` | Reload config from disk (re-reads global + project). |
| `/dc mode <mode>` | Switch mode (`off`/`yolo`/`blacklist`/`whitelist`/`ask`). |
| `/dc mode reset` | Drop the runtime mode override, return to the configured `mode`. |
| `/dc reset` / `/dc clear` | Same as `mode reset`. |
| `/dc cycle` | Step to the next mode in `cycleModes`. |
| `/dc rules` | List loaded rules (`action  id`). |

Mode changes are **in-memory only** — they reset to the configured `mode` on the next
session. There is no persisted state file.

---

## Notes & limitations

- **Keymaps are bound once** from the global config at startup. Changing `keymaps` or
  setting project-level keymaps requires a restart (the extension API has no rebind).
- Dialogs and logged decisions clip long inputs, so a `write` payload never dumps its
  full contents into the UI or transcript.

See [`AUDIT_REPORT.md`](./AUDIT_REPORT.md) for the current state of known issues and
planned improvements.
