#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import zipfile
from functools import lru_cache
from pathlib import Path
from shutil import which
from typing import Any, Iterable, Sequence

FAILURE_CONCLUSIONS = {
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
}

FAILURE_STATES = {
    "failure",
    "error",
    "cancelled",
    "timed_out",
    "action_required",
}

FAILURE_BUCKETS = {"fail"}

FAILURE_MARKERS = (
    "error",
    "fail",
    "failed",
    "traceback",
    "exception",
    "assert",
    "panic",
    "fatal",
    "timeout",
    "segmentation fault",
)

# Patterns that indicate a command's output was redirected to a file instead of stdout.
# When these appear in the log, the actual failure detail is NOT in the log itself.
REDIRECTED_OUTPUT_PATTERNS = (
    r">\s*\S+\.txt\s+2>&1",
    r"2>&1\s*\|\s*tee\s+\S+",
    r">\s*result\.\w+",
)

DEFAULT_MAX_LINES = 100
DEFAULT_CONTEXT_LINES = 30
DEFAULT_MAX_FAILURES = 3

# When set, overrides the repo slug derived from the local git context.
# Used for cross-repo inspection (e.g. the agent is in repo A but inspecting repo B's CI).
_REPO_SLUG_OVERRIDE: str | None = None

PENDING_LOG_MARKERS = (
    "still in progress",
    "log will be available when it is complete",
)


class GhResult:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_gh_command(args: Sequence[str], cwd: Path) -> GhResult:
    process = subprocess.run(
        ["gh", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    return GhResult(process.returncode, process.stdout, process.stderr)


def run_gh_command_raw(args: Sequence[str], cwd: Path) -> tuple[int, bytes, str]:
    process = subprocess.run(
        ["gh", *args],
        cwd=cwd,
        capture_output=True,
    )
    stderr = process.stderr.decode(errors="replace")
    return process.returncode, process.stdout, stderr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect failing GitHub Actions checks from a PR, run, job, or Actions URL "
            "and extract actionable failure context."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--repo", default=".", help="Path inside the target Git repository."
    )
    parser.add_argument(
        "--pr", default=None, help="PR number or URL (defaults to current branch PR)."
    )
    parser.add_argument("--run", default=None, help="GitHub Actions run id.")
    parser.add_argument("--job", default=None, help="GitHub Actions job id.")
    parser.add_argument(
        "--url",
        default=None,
        help="GitHub Actions run/job URL or PR URL. Useful when pasting a failing check link.",
    )
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    parser.add_argument("--context", type=int, default=DEFAULT_CONTEXT_LINES)
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of text output."
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=DEFAULT_MAX_FAILURES,
        help="Maximum number of failing jobs to analyze per run.",
    )
    parser.add_argument(
        "--repo-slug",
        default=None,
        metavar="OWNER/REPO",
        help=(
            "Override the repository slug used for GitHub API calls "
            "(e.g. 'owner/repo-name'). Use when inspecting a repo "
            "different from the one your current directory belongs to."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = find_git_root(Path(args.repo))
    if repo_root is None:
        print("Error: not inside a Git repository.", file=sys.stderr)
        return 1

    if not ensure_gh_available(repo_root):
        return 1

    # Resolve the repo slug early so all subsequent API calls use the right repo.
    # Priority: explicit --repo-slug > slug extracted from any GitHub URL > local git context.
    global _REPO_SLUG_OVERRIDE
    if args.repo_slug:
        _REPO_SLUG_OVERRIDE = args.repo_slug
    else:
        for url_candidate in filter(None, [args.url, args.pr]):
            slug = extract_repo_from_url(str(url_candidate))
            if slug:
                _REPO_SLUG_OVERRIDE = slug
                break

    run_id, job_id, pr_value = resolve_explicit_target(
        pr_value=args.pr,
        run_value=args.run,
        job_value=args.job,
        url_value=args.url,
    )

    results: list[dict[str, Any]]
    target_label: str

    if job_id:
        results = [
            analyze_job(
                job_id=job_id,
                repo_root=repo_root,
                max_lines=max(1, args.max_lines),
                context=max(1, args.context),
                pr_value=pr_value,
                run_id=run_id,
                details_url=args.url,
            )
        ]
        target_label = f"job {job_id}"
    elif run_id:
        results = analyze_run(
            run_id=run_id,
            repo_root=repo_root,
            max_lines=max(1, args.max_lines),
            context=max(1, args.context),
            pr_value=pr_value,
            prefer_url=args.url,
            max_failures=args.max_failures,
        )
        target_label = f"run {run_id}"
    else:
        pr_value = resolve_pr(pr_value, repo_root)
        if pr_value is None:
            return 1

        checks = fetch_checks(pr_value, repo_root)
        if checks is None:
            return 1

        failing = [c for c in checks if is_failing(c)][: args.max_failures]
        if not failing:
            print(f"PR #{pr_value}: no failing checks detected.")
            return 0

        results = []
        for check in failing:
            results.append(
                analyze_check(
                    check,
                    repo_root=repo_root,
                    max_lines=max(1, args.max_lines),
                    context=max(1, args.context),
                    pr_value=pr_value,
                )
            )
        target_label = f"PR #{pr_value}"

    failing_results = [result for result in results if result_indicates_failure(result)]
    if not failing_results:
        print(f"{target_label}: no failing GitHub Actions jobs detected.")
        return 0

    if args.json:
        print(
            json.dumps(
                {
                    "target": target_label,
                    "pr": pr_value,
                    "runId": run_id,
                    "jobId": job_id,
                    "results": failing_results,
                },
                indent=2,
            )
        )
    else:
        render_results(target_label, failing_results)

    return 1


def resolve_explicit_target(
    *,
    pr_value: str | None,
    run_value: str | None,
    job_value: str | None,
    url_value: str | None,
) -> tuple[str | None, str | None, str | None]:
    run_id = run_value
    job_id = job_value
    resolved_pr = pr_value

    if url_value:
        extracted_run_id = extract_run_id(url_value)
        extracted_job_id = extract_job_id(url_value)
        extracted_pr = extract_pr_number(url_value)
        run_id = run_id or extracted_run_id
        job_id = job_id or extracted_job_id
        resolved_pr = resolved_pr or extracted_pr
        if run_id is None and job_id is None and extracted_pr and pr_value is None:
            return None, None, extracted_pr

    return run_id, job_id, resolved_pr


def find_git_root(start: Path) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def ensure_gh_available(repo_root: Path) -> bool:
    if which("gh") is None:
        print("Error: gh is not installed or not on PATH.", file=sys.stderr)
        return False
    result = run_gh_command(["auth", "status"], cwd=repo_root)
    if result.returncode == 0:
        return True
    message = (result.stderr or result.stdout or "").strip()
    print(message or "Error: gh not authenticated.", file=sys.stderr)
    return False


def resolve_pr(pr_value: str | None, repo_root: Path) -> str | None:
    if pr_value:
        return pr_value
    result = run_gh_command(["pr", "view", "--json", "number"], cwd=repo_root)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        print(message or "Error: unable to resolve PR.", file=sys.stderr)
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        print("Error: unable to parse PR JSON.", file=sys.stderr)
        return None
    number = data.get("number")
    if not number:
        print("Error: no PR number found.", file=sys.stderr)
        return None
    return str(number)


def fetch_checks(pr_value: str, repo_root: Path) -> list[dict[str, Any]] | None:
    primary_fields = [
        "name",
        "state",
        "conclusion",
        "detailsUrl",
        "startedAt",
        "completedAt",
    ]
    result = run_gh_command(
        ["pr", "checks", pr_value, "--json", ",".join(primary_fields)],
        cwd=repo_root,
    )
    if result.returncode != 0:
        message = "\n".join(filter(None, [result.stderr, result.stdout])).strip()
        available_fields = parse_available_fields(message)
        if available_fields:
            fallback_fields = [
                "name",
                "state",
                "bucket",
                "link",
                "startedAt",
                "completedAt",
                "workflow",
            ]
            selected_fields = [
                field for field in fallback_fields if field in available_fields
            ]
            if not selected_fields:
                print(
                    "Error: no usable fields available for gh pr checks.",
                    file=sys.stderr,
                )
                return None
            result = run_gh_command(
                ["pr", "checks", pr_value, "--json", ",".join(selected_fields)],
                cwd=repo_root,
            )
            if result.returncode != 0:
                message = (result.stderr or result.stdout or "").strip()
                print(message or "Error: gh pr checks failed.", file=sys.stderr)
                return None
        else:
            print(message or "Error: gh pr checks failed.", file=sys.stderr)
            return None
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        print("Error: unable to parse checks JSON.", file=sys.stderr)
        return None
    if not isinstance(data, list):
        print("Error: unexpected checks JSON shape.", file=sys.stderr)
        return None
    return data


def is_failing(check: dict[str, Any]) -> bool:
    conclusion = normalize_field(check.get("conclusion"))
    if conclusion in FAILURE_CONCLUSIONS:
        return True
    state = normalize_field(check.get("state") or check.get("status"))
    if state in FAILURE_STATES:
        return True
    bucket = normalize_field(check.get("bucket"))
    return bucket in FAILURE_BUCKETS


def is_failing_job(job: dict[str, Any]) -> bool:
    conclusion = normalize_field(job.get("conclusion"))
    if conclusion in FAILURE_CONCLUSIONS:
        return True
    status = normalize_field(job.get("status"))
    return status in FAILURE_STATES


def result_indicates_failure(result: dict[str, Any]) -> bool:
    status = normalize_field(result.get("status"))
    return status not in {"external", "skipped"}


def analyze_check(
    check: dict[str, Any],
    repo_root: Path,
    max_lines: int,
    context: int,
    pr_value: str | None = None,
) -> dict[str, Any]:
    url = check.get("detailsUrl") or check.get("link") or ""
    run_id = extract_run_id(url)
    job_id = extract_job_id(url)
    base: dict[str, Any] = {
        "name": check.get("name", ""),
        "detailsUrl": url,
        "runId": run_id,
        "jobId": job_id,
    }

    if run_id is None:
        base["status"] = "external"
        base["note"] = "No GitHub Actions run id detected in detailsUrl."
        return base

    metadata = fetch_run_metadata(run_id, repo_root)
    log_text, log_error, log_status = fetch_check_log(
        run_id=run_id,
        job_id=job_id,
        repo_root=repo_root,
    )

    if log_status == "pending":
        base["status"] = "log_pending"
        base["note"] = log_error or "Logs are not available yet."
        if metadata:
            base["run"] = metadata
        return base

    if log_error:
        base["status"] = "log_unavailable"
        base["error"] = log_error
        if metadata:
            base["run"] = metadata
        return base

    snippet = extract_failure_snippet(log_text, max_lines=max_lines, context=context)
    base["status"] = "ok"
    base["run"] = metadata or {}
    base["logSnippet"] = snippet

    # Detect when the failing command redirected its output to a file.
    # The actual failure detail won't be in the log — surface alternative sources.
    if has_redirected_output(log_text):
        base["redirectedOutputWarning"] = (
            "The failing command redirected its output to a file (e.g. '> result.txt'). "
            "The log snippet above does NOT contain the actual failure detail. "
            "Check PR comments or CI artifacts for the real output."
        )
        artifacts = fetch_run_artifacts(run_id, repo_root)
        if artifacts:
            base["artifacts"] = [
                {"name": a.get("name"), "id": a.get("id"), "expired": a.get("expired")}
                for a in artifacts
            ]
        if pr_value:
            bot_comments = fetch_pr_bot_comments(pr_value, repo_root)
            if bot_comments:
                # Surface the most recent bot comment — most likely to contain the result
                base["latestBotComment"] = bot_comments[0][:4000]

    return base


def analyze_run(
    *,
    run_id: str,
    repo_root: Path,
    max_lines: int,
    context: int,
    pr_value: str | None = None,
    prefer_url: str | None = None,
    max_failures: int = DEFAULT_MAX_FAILURES,
) -> list[dict[str, Any]]:
    metadata = fetch_run_metadata(run_id, repo_root) or {}
    jobs = fetch_run_jobs(run_id, repo_root)
    failing_jobs = [job for job in jobs if is_failing_job(job)][:max_failures]

    if failing_jobs:
        return [
            analyze_job(
                job_id=str(job.get("id")),
                repo_root=repo_root,
                max_lines=max_lines,
                context=context,
                pr_value=pr_value,
                run_id=run_id,
                job_data=job,
                details_url=job.get("html_url") or prefer_url,
            )
            for job in failing_jobs
            if job.get("id")
        ]

    log_text, log_error, log_status = fetch_check_log(
        run_id=run_id,
        job_id=None,
        repo_root=repo_root,
    )
    result: dict[str, Any] = {
        "name": metadata.get("workflowName") or metadata.get("name") or f"run {run_id}",
        "detailsUrl": prefer_url or metadata.get("url") or "",
        "runId": run_id,
        "jobId": None,
        "run": metadata,
    }

    if log_status == "pending":
        result["status"] = "log_pending"
        result["note"] = log_error or "Logs are not available yet."
        return [result]

    if log_error:
        result["status"] = "log_unavailable"
        result["error"] = log_error
        return [result]

    result["status"] = "ok"
    result["logSnippet"] = extract_failure_snippet(
        log_text, max_lines=max_lines, context=context
    )
    if has_redirected_output(log_text):
        enrich_redirected_output(
            result,
            log_text=log_text,
            run_id=run_id,
            repo_root=repo_root,
            pr_value=pr_value,
        )
    return [result]


def analyze_job(
    *,
    job_id: str,
    repo_root: Path,
    max_lines: int,
    context: int,
    pr_value: str | None = None,
    run_id: str | None = None,
    job_data: dict[str, Any] | None = None,
    details_url: str | None = None,
) -> dict[str, Any]:
    job = job_data or fetch_job_metadata(job_id, repo_root) or {}
    resolved_run_id = run_id or extract_run_id(details_url or "") or derive_run_id_from_job(
        job, repo_root
    )
    metadata = fetch_run_metadata(resolved_run_id, repo_root) if resolved_run_id else None

    base: dict[str, Any] = {
        "name": job.get("name") or f"job {job_id}",
        "detailsUrl": details_url or job.get("html_url") or "",
        "runId": resolved_run_id,
        "jobId": job_id,
        "run": metadata or {},
        "job": {
            k: job[k]
            for k in ("conclusion", "status", "started_at", "completed_at", "name")
            if k in job
        },
    }

    log_text, log_error = fetch_job_log(job_id, repo_root)
    if log_error and is_log_pending_message(log_error):
        base["status"] = "log_pending"
        base["note"] = log_error
        return base
    if log_error:
        base["status"] = "log_unavailable"
        base["error"] = log_error
        return base

    base["status"] = "ok"
    base["logSnippet"] = extract_failure_snippet(log_text, max_lines=max_lines, context=context)
    if has_redirected_output(log_text) and resolved_run_id:
        enrich_redirected_output(
            base,
            log_text=log_text,
            run_id=resolved_run_id,
            repo_root=repo_root,
            pr_value=pr_value,
        )
    return base


def extract_run_id(url: str) -> str | None:
    if not url:
        return None
    for pattern in (r"/actions/runs/(\d+)", r"/runs/(\d+)"):
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_job_id(url: str) -> str | None:
    if not url:
        return None
    match = re.search(r"/actions/runs/\d+/job/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"/job/(\d+)", url)
    if match:
        return match.group(1)
    return None


def extract_pr_number(url: str) -> str | None:
    if not url:
        return None
    match = re.search(r"/pull/(\d+)", url)
    if match:
        return match.group(1)
    return None


def fetch_run_metadata(run_id: str, repo_root: Path) -> dict[str, Any] | None:
    fields = [
        "conclusion",
        "status",
        "workflowName",
        "name",
        "event",
        "headBranch",
        "headSha",
        "url",
    ]
    result = run_gh_command(
        ["run", "view", run_id, "--json", ",".join(fields)], cwd=repo_root
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def fetch_run_jobs(run_id: str, repo_root: Path) -> list[dict[str, Any]]:
    repo_slug = fetch_repo_slug(repo_root)
    if not repo_slug:
        return []
    endpoint = f"/repos/{repo_slug}/actions/runs/{run_id}/jobs?per_page=100"
    result = run_gh_command(["api", endpoint], cwd=repo_root)
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return []
    jobs = data.get("jobs", [])
    return jobs if isinstance(jobs, list) else []


def fetch_job_metadata(job_id: str, repo_root: Path) -> dict[str, Any] | None:
    repo_slug = fetch_repo_slug(repo_root)
    if not repo_slug:
        return None
    endpoint = f"/repos/{repo_slug}/actions/jobs/{job_id}"
    result = run_gh_command(["api", endpoint], cwd=repo_root)
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def derive_run_id_from_job(job: dict[str, Any], repo_root: Path) -> str | None:
    html_url = str(job.get("html_url") or "")
    run_id = extract_run_id(html_url)
    if run_id:
        return run_id

    check_run_url = str(job.get("check_run_url") or "")
    match = re.search(r"/check-runs/(\d+)", check_run_url)
    if not match:
        return None

    repo_slug = fetch_repo_slug(repo_root)
    if not repo_slug:
        return None
    endpoint = f"/repos/{repo_slug}/check-runs/{match.group(1)}"
    result = run_gh_command(["api", endpoint], cwd=repo_root)
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    details_url = str(data.get("details_url") or "")
    return extract_run_id(details_url)


def fetch_check_log(
    run_id: str,
    job_id: str | None,
    repo_root: Path,
) -> tuple[str, str, str]:
    if job_id:
        job_log, job_error = fetch_job_log(job_id, repo_root)
        if job_log:
            return job_log, "", "ok"
        if job_error and is_log_pending_message(job_error):
            return "", job_error, "pending"

        if job_error:
            return "", job_error, "error"

    log_text, log_error = fetch_run_log(run_id, repo_root)
    if not log_error:
        return log_text, "", "ok"

    if is_log_pending_message(log_error):
        return "", log_error, "pending"

    return "", log_error, "error"


def fetch_run_log(run_id: str, repo_root: Path) -> tuple[str, str]:
    result = run_gh_command(["run", "view", run_id, "--log"], cwd=repo_root)
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "").strip()
        return "", error or "gh run view failed"
    return result.stdout, ""


def fetch_job_log(job_id: str, repo_root: Path) -> tuple[str, str]:
    repo_slug = fetch_repo_slug(repo_root)
    if not repo_slug:
        return "", "Error: unable to resolve repository name for job logs."
    endpoint = f"/repos/{repo_slug}/actions/jobs/{job_id}/logs"
    returncode, stdout_bytes, stderr = run_gh_command_raw(
        ["api", endpoint], cwd=repo_root
    )
    if returncode != 0:
        message = (stderr or stdout_bytes.decode(errors="replace")).strip()
        return "", message or "gh api job logs failed"
    if is_zip_payload(stdout_bytes):
        extracted = extract_text_from_zip(stdout_bytes)
        if extracted:
            return extracted, ""
        return "", "Job logs returned a zip archive; unable to parse."
    return stdout_bytes.decode(errors="replace"), ""


def extract_text_from_zip(payload: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            text_chunks = []
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                with archive.open(name) as handle:
                    text_chunks.append(handle.read().decode(errors="replace"))
            return "\n".join(chunk for chunk in text_chunks if chunk)
    except zipfile.BadZipFile:
        return ""


def extract_repo_from_url(url: str) -> str | None:
    """Parse owner/repo from a GitHub URL (PR, Actions run/job, or bare repo URL)."""
    if not url:
        return None
    match = re.search(r"github\.com/([^/]+)/([^/?#]+)", url)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return None


def fetch_repo_slug(repo_root: Path) -> str | None:
    if _REPO_SLUG_OVERRIDE is not None:
        return _REPO_SLUG_OVERRIDE
    return _fetch_repo_slug_from_git(repo_root)


@lru_cache(maxsize=None)
def _fetch_repo_slug_from_git(repo_root: Path) -> str | None:
    result = run_gh_command(["repo", "view", "--json", "nameWithOwner"], cwd=repo_root)
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    name_with_owner = data.get("nameWithOwner")
    if not name_with_owner:
        return None
    return str(name_with_owner)


def normalize_field(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def parse_available_fields(message: str) -> list[str]:
    if "Available fields:" not in message:
        return []
    fields: list[str] = []
    collecting = False
    for line in message.splitlines():
        if "Available fields:" in line:
            collecting = True
            continue
        if not collecting:
            continue
        field = line.strip()
        if not field:
            continue
        fields.append(field)
    return fields


def is_log_pending_message(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in PENDING_LOG_MARKERS)


def is_zip_payload(payload: bytes) -> bool:
    return payload.startswith(b"PK")


def has_redirected_output(log_text: str) -> bool:
    """Return True if the log contains a command that redirects its output to a file.

    When this is detected the real failure detail won't be visible in the log —
    it will be in a PR comment or a CI artifact instead.
    """
    for pattern in REDIRECTED_OUTPUT_PATTERNS:
        if re.search(pattern, log_text):
            return True
    return False


def enrich_redirected_output(
    result: dict[str, Any],
    *,
    log_text: str,
    run_id: str,
    repo_root: Path,
    pr_value: str | None,
) -> None:
    result["redirectedOutputWarning"] = (
        "The failing command redirected its output to a file. "
        "The log snippet may not contain the real failure detail."
    )
    artifacts = fetch_run_artifacts(run_id, repo_root)
    if artifacts:
        result["artifacts"] = [
            {"name": a.get("name"), "id": a.get("id"), "expired": a.get("expired")}
            for a in artifacts
        ]
    if pr_value:
        bot_comments = fetch_pr_bot_comments(pr_value, repo_root)
        if bot_comments:
            result["latestBotComment"] = bot_comments[0][:4000]


def fetch_pr_bot_comments(pr_value: str, repo_root: Path) -> list[str]:
    """Return the bodies of bot comments on the PR, most-recent first.

    Useful when a workflow step posts its result as a PR comment instead of
    printing it to stdout.
    """
    repo_slug = fetch_repo_slug(repo_root)
    if not repo_slug:
        return []
    endpoint = f"/repos/{repo_slug}/issues/{pr_value}/comments"
    result = run_gh_command(["api", endpoint], cwd=repo_root)
    if result.returncode != 0:
        return []
    try:
        comments = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(comments, list):
        return []
    bot_comments = [
        c.get("body", "")
        for c in reversed(comments)
        if "[bot]" in (c.get("user", {}).get("login") or "")
        and c.get("body", "").strip()
    ]
    return bot_comments


def fetch_run_artifacts(run_id: str, repo_root: Path) -> list[dict[str, Any]]:
    """Return the list of artifact metadata for a run."""
    repo_slug = fetch_repo_slug(repo_root)
    if not repo_slug:
        return []
    endpoint = f"/repos/{repo_slug}/actions/runs/{run_id}/artifacts"
    result = run_gh_command(["api", endpoint], cwd=repo_root)
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return []
    return data.get("artifacts", [])


def extract_failure_snippet(log_text: str, max_lines: int, context: int) -> str:
    lines = log_text.splitlines()
    if not lines:
        return ""

    marker_index = find_failure_index(lines)
    if marker_index is None:
        return "\n".join(lines[-max_lines:])

    start = max(0, marker_index - context)
    end = min(len(lines), marker_index + context)
    window = lines[start:end]
    if len(window) > max_lines:
        window = window[-max_lines:]
    return "\n".join(window)


def find_failure_index(lines: Sequence[str]) -> int | None:
    for idx in range(len(lines) - 1, -1, -1):
        lowered = lines[idx].lower()
        if any(marker in lowered for marker in FAILURE_MARKERS):
            return idx
    return None


def render_results(target_label: str, results: Iterable[dict[str, Any]]) -> None:
    results_list = list(results)
    print(f"{target_label}: {len(results_list)} failing checks analyzed.")
    for result in results_list:
        print("-" * 60)
        print(f"Check: {result.get('name', '')}")
        if result.get("detailsUrl"):
            print(f"Details: {result['detailsUrl']}")
        run_id = result.get("runId")
        if run_id:
            print(f"Run ID: {run_id}")
        job_id = result.get("jobId")
        if job_id:
            print(f"Job ID: {job_id}")
        status = result.get("status", "unknown")
        print(f"Status: {status}")

        run_meta = result.get("run", {})
        if run_meta:
            branch = run_meta.get("headBranch", "")
            sha = (run_meta.get("headSha") or "")[:12]
            workflow = run_meta.get("workflowName") or run_meta.get("name") or ""
            conclusion = run_meta.get("conclusion") or run_meta.get("status") or ""
            print(f"Workflow: {workflow} ({conclusion})")
            if branch or sha:
                print(f"Branch/SHA: {branch} {sha}")
            if run_meta.get("url"):
                print(f"Run URL: {run_meta['url']}")

        job_meta = result.get("job", {})
        if job_meta:
            conclusion = job_meta.get("conclusion") or job_meta.get("status") or ""
            started_at = job_meta.get("started_at") or ""
            completed_at = job_meta.get("completed_at") or ""
            if conclusion:
                print(f"Job Conclusion: {conclusion}")
            if started_at or completed_at:
                print(f"Job Timing: {started_at} -> {completed_at}")

        if result.get("note"):
            print(f"Note: {result['note']}")

        if result.get("error"):
            print(f"Error fetching logs: {result['error']}")
            continue

        snippet = result.get("logSnippet") or ""
        if snippet:
            print("Failure snippet:")
            print(indent_block(snippet, prefix="  "))
        else:
            print("No snippet available.")

        warning = result.get("redirectedOutputWarning")
        if warning:
            print(f"WARNING: {warning}")

        artifacts = result.get("artifacts")
        if artifacts:
            print("CI artifacts available:")
            for a in artifacts:
                expired = " (expired)" if a.get("expired") else ""
                print(f"  - {a.get('name')} (id={a.get('id')}){expired}")

        latest_comment = result.get("latestBotComment")
        if latest_comment:
            print(
                "Latest bot comment on PR (likely contains the actual failure output):"
            )
            print(indent_block(latest_comment, prefix="  "))

    print("-" * 60)


def indent_block(text: str, prefix: str = "  ") -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


if __name__ == "__main__":
    raise SystemExit(main())
