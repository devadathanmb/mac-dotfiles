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
- Active branch/model's cumulative prompt-cache hit ratio, estimated TTL
  countdown, total recorded session cost, and wall-clock session age.
  Cost includes recorded tool/compaction usage.
- Working directory, Git branch, dirty marker, upstream ahead/behind, and
  tracked additions/deletions vs HEAD (staged and unstaged combined).
  Untracked files set the dirty marker but do not contribute line counts.
- Provider quota meters and reset times through normalized usage adapters.
- Guardrails configuration status, including a prominent bypass warning, and other extensions' status text below the two rows.

`Ctrl+Alt+G` or `/guardrails-toggle` toggles Guardrails globally and reloads Pi. The setting persists across sessions. The toggle refuses to change a trusted project's explicit `enabled` override; use `/guardrails:settings` for that. Status reflects saved global and trusted-project settings, not temporary in-memory overrides or the presence of other safety extensions. The command gate may be disabled separately, which is shown in the footer.

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

## Prompt cache

Examples: `cache 99% ~29m`, `cache 92% TTL elapsed`,
`cache 85% miss`, or `cache 99% TTL ?`. Run `/cache` for the source and
limitations of the current estimate.

`cache.ts` observes `before_provider_request` without changing requests and
uses raw usage events to refine retention. The ratio is cache reads divided
by ordinary input + cache reads + cache writes, cumulative for successful
responses from the selected provider/model on the **active branch**. It is
not a prediction of the next request's hit rate. Errors, aborted messages,
tool calls' nested usage, and cache-warming requests do not inflate it.
This matches Claude Code's cumulative-ratio convention rather than the old
footer's latest-response-only percentage.

Claude Code's status-line `prompt_cache.expires_at` is **computed by Claude
Code**, not an expiry timestamp returned by Anthropic's Messages API. Pi's
normalized usage likewise contains token counts, not an expiry deadline.

- **OpenAI Responses, official origin, explicit-cache-capable model:**
  default minimum coverage is 30m. Reads refresh at least 30m, even when the
  original entry was written for 12h. A raw response reporting exclusively
  12h writes and no reads gives a 12h minimum-coverage estimate. Mixed
  prefixes/read-write requests use the conservative 30m window. Explicit-only
  mode without breakpoints does not establish a write lifetime.
- **Older OpenAI models:** `in_memory` and `24h` are variable-retention
  policies, not precise countdowns. Show `TTL ?` and explain `/cache`:
  in-memory typically 5–10m idle (up to 1h); extended typically ~30m
  (up to 24h). Do not convert `24h` into a guaranteed day-long timer.
- **Unknown providers, proxies, transports, or unsupported TTLs:** show
  `TTL ?`, never assume OpenAI semantics based on a model name.
  Anthropic-specific cache TTL tracking is not implemented.

`~` explicitly marks a local estimate, measured from request start (not
stream completion). After that window, `TTL elapsed` does **not** claim the
server evicted every prefix: minimum coverage may have ended while entries
survive, and routing/prompt changes can also prevent reuse before then.
`miss` means the last successful response reported no cache reads or writes,
not a diagnosed unexpected miss. Initial cache writes count as caching.

Only small policy/timing records are persisted in `footer-cache-v1` session
entries: no prompt, payload, headers, credentials, or network calls. Reload
and resume restore the original deadline, not a fresh timer. Metadata is
isolated by provider, model, API, and endpoint. Historical sessions without
these records show the ratio with `TTL ?` until another request is observed.
Pi's persisted `cache_warm` usage is recognized, but it lacks request-start
and endpoint metadata, so it makes the refreshed deadline unknown instead of
showing a stale elapsed timer or inventing a new one. This extension does not
initiate keepalive requests or change Pi's warming decisions.

The footer refreshes every five seconds, including while idle. Narrow layouts
retain the cache state along with its percentage until the cache segment must
be dropped altogether.

Sources (checked against Pi 1.5.0's installed provider implementations):
- https://code.claude.com/docs/en/statusline#prompt-cache-fields
- https://developers.openai.com/api/docs/guides/prompt-caching
- Local Pi: `pi-ai/dist/api/openai-responses.js`,
  `openai-responses-shared.js`, and
  `pi-coding-agent/dist/core/cache-warmer.js`.

## Disable

Move this directory out of `~/.pi/agent/extensions/`, then `/reload`.

## Test

Point `PI_PACKAGE` at the installed `@earendil-works/pi-coding-agent` directory:

```sh
PI_PACKAGE=/path/to/node_modules/@earendil-works/pi-coding-agent \
  node ~/.pi/agent/extensions/footer/test.mjs
```

Tests use mocked model/provider data, not paid model requests.
