---
name: "gh-fix-ci"
description: "Go-to skill for getting CI/PR failure context using the GitHub CLI. Use whenever a user shares a failing GitHub Actions link, asks why a PR is failing, wants to inspect or fix a failing check, test, or workflow run, or asks about CI status on a PR. Covers: fetching GitHub Actions logs, extracting failure snippets, reading PR bot comments, listing CI artifacts, and proposing a fix. Triggers on: 'fix CI', 'checks are failing', 'PR is red', 'why is this failing', 'inspect the failing test', 'GitHub Actions error', or any GitHub Actions/PR URL."
---

# Gh Fix CI

## Overview

Use the bundled script to locate failing GitHub Actions checks, extract failure context, summarize the root cause, and propose a targeted fix — implementing only after explicit approval.

## Workflow

1. **Resolve the target.**
   - If the user provides a PR number/URL, run id, job id, or GitHub Actions URL, use that directly.
   - Otherwise use the current branch PR (the script will auto-detect it).

2. **Run the inspector script with `--json`.**
   Always pass `--json` so output is structured and parseable — do not omit it.
   ```
   python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "<number-or-url>" --json
   python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --run "<run-id>" --json
   python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --job "<job-id>" --json
   python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --url "<github-actions-url>" --json
   ```
   The script handles gh authentication, field drift, log fetching, pending log detection, redirected-output detection, artifacts, and PR bot comments automatically. Do not re-implement any of this manually.

   **Cross-repo usage**: if you are not inside the target repository's directory, the script auto-detects the repo from any full GitHub URL passed via `--pr` or `--url`. If no URL is available (e.g. bare PR number only), add `--repo-slug owner/repo` explicitly:
   ```
   python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "123" --repo-slug "owner/repo-name" --json
   ```

   - Exit code 0 → no failures. Report that clearly and stop.
   - Exit code 1 → failures found. Parse the JSON and continue.
   - If the script itself errors (non-JSON output to stderr), report the raw error to the user.

3. **Summarize failures.**
   From the JSON `results` array, for each item:
   - Report: check/job name, run URL (`detailsUrl`), and the `logSnippet` (the extracted failure context).
   - If `redirectedOutputWarning` is set, the snippet may be empty — surface `latestBotComment` or list `artifacts` instead.
   - Skip items with `status: "external"` (not GitHub Actions — just show the URL).
   - Note items with `status: "log_pending"` (logs not yet available).
   - Do not paste the raw JSON — synthesize a readable summary.

4. **Propose a fix plan and implement after approval.**
   - Draft a concise plan describing what to change and why.
   - Ask for explicit approval before touching any files.
   - After approval: apply the fix, summarize diffs, and ask about opening a PR.
   - Suggest re-running relevant tests and `gh pr checks` to confirm.

## Scope

GitHub Actions only. Checks whose `detailsUrl` contains no GitHub Actions run ID are marked external and skipped — only their URL is reported.

## Bundled Resources

### scripts/inspect_pr_checks.py

Fetches failing GitHub Actions checks, run/job logs, and extracts a failure snippet. Handles gh authentication, field drift, zip archives, redirected output, pending logs, PR bot comments, and CI artifacts. Exits non-zero when failures are detected.

Arguments:
- `--repo PATH` — path inside the target Git repository (default: `.`)
- `--pr NUMBER_OR_URL` — PR number or URL (defaults to current branch PR)
- `--run RUN_ID` — GitHub Actions run id
- `--job JOB_ID` — GitHub Actions job id
- `--url URL` — any GitHub Actions or PR URL (run, job, or pull request)
- `--max-lines N` — log lines in failure snippet (default: 100)
- `--context N` — context lines around failure marker (default: 30)
- `--max-failures N` — max failing jobs to analyze per invocation (default: 3)
- `--repo-slug OWNER/REPO` — override the repo slug for API calls (auto-detected from GitHub URLs; only needed when passing a bare PR number from outside the target repo)
- `--json` — emit structured JSON (always use this)
