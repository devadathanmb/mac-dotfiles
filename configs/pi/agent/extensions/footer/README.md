# Pi footer

Automatically loaded globally from `~/.pi/agent/extensions/footer/index.ts`.
Run `/reload` in an existing Pi session to enable changes.

Two rows, neutral grays, lavender model/context accents, thin meters,
threshold colors, and right-aligned provider usage. No dependencies to install
and no changes to Pi's installed package.

## Data shown

- Model display name and current thinking level.
- Context meter, percentage, and used/maximum tokens. Unknown post-compaction
  usage is displayed as `?`, not zero.
- Latest response's prompt-cache hit ratio, total recorded session cost,
  and wall-clock session age. Cost includes recorded tool/compaction usage.
- Working directory, Git branch, dirty marker, upstream ahead/behind, and
  tracked additions/deletions vs HEAD (staged and unstaged combined).
  Untracked files set the dirty marker but do not contribute line counts.
- Provider quota meters and reset times through normalized usage adapters.
- Other extensions' status text below the two rows.

Git refreshes asynchronously every five seconds. Rendering never launches
subprocesses or network requests. Output adapts to narrow widths and Unicode.

## Provider usage

`usage.ts` normalizes provider responses into common limit windows, independent
of the renderer. Data can arrive through response headers, provider stream
events, or authenticated usage endpoint polling.

- **OpenAI subscription:** polls the same `/backend-api/wham/usage` endpoint
  used by Codex's `account/rateLimits/read`. Also consumes Codex quota headers
  and `codex.rate_limits` stream events.
- **Anthropic subscription:** polls `/api/oauth/usage` with the OAuth beta
  header. This is an internal, undocumented endpoint and may change. Unified
  quota response headers also work.
- **API throughput:** recognizes OpenAI-compatible request/token rate-limit
  headers and Anthropic API headers. These meters are explicitly labeled
  `req`/`tok`, not `5h`/`7d`: API throughput is not subscription allowance.
- **Other providers:** compatible headers work automatically. Additional
  subscription endpoints can be added to the adapter registry.

Usage endpoint polling requires Pi OAuth credentials for the selected provider
and a matching official inference origin. It resolves auth through Pi's model
registry (including normal token refresh); it does not read another app's
credentials or send API keys to subscription endpoints. Polling is at most once
per minute per model/provider/endpoint, with longer backoff for errors. Requests
time out after ten seconds and are aborted on shutdown. 401/403 responses do not
cause repeated login prompts or refresh loops.

Snapshots are isolated by provider, model, and inference endpoint. Stale or reset
windows are not presented as current. Provider changes cannot display another
provider's quota. Pending requests are deduplicated.

### OpenAI token-sharing limitation

The `openai` provider's newer Sign in with ChatGPT token-sharing login is not
the same credential as a Codex OAuth login. OpenAI currently rejects this
login at the Codex usage endpoint. A live check on this machine returned HTTP
401, type `rejected_by_access_enforcement`, code `no_matching_rule`.
This is an upstream access restriction, not evidence of zero usage.

When no quota is exposed, the right column shows a usage-settings link instead
of silently disappearing. Run `/usage` for a forced refresh and an explanation.
The command never changes billing or consumes a rate-limit reset credit.

References:
- https://developers.openai.com/codex/app-server (account/rateLimits/read)
- https://developers.openai.com/api/docs/guides/rate-limits (API headers)
- https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery
- https://github.com/openai/codex/issues/54219 (token-sharing usage access)
- https://github.com/openai/codex/blob/main/codex-rs/backend-client/src/client/rate_limit_resets.rs
- https://github.com/FullFran/claudeops-tui/blob/main/docs/oauth-usage-endpoint.md

Cache expiry countdowns are not shown: cache hit ratio does not establish
cache retention or expiration. No synthetic usage or reset times are displayed.

## Disable

Move this directory out of `~/.pi/agent/extensions/`, then `/reload`.

## Test

Point `PI_PACKAGE` at the installed `@earendil-works/pi-coding-agent` directory:

```sh
PI_PACKAGE=/path/to/node_modules/@earendil-works/pi-coding-agent \
  node ~/.pi/agent/extensions/footer/test.mjs
```

Tests use mocked model/provider data, not paid model requests.
