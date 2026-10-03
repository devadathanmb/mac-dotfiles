#!/usr/bin/env python3
"""research — agent-oriented research CLI (Context7, Exa, DeepWiki, grep.app).

Talks to the services' remote MCP endpoints directly (JSON-RPC over HTTP, stdlib only).

Output contract (designed for LLM agents):
  * Small results print inline.
  * Large results print a short preview plus the path of a file holding the FULL
    output, so the agent can Read/rg exactly the part it needs.
  * Errors are one line on stderr (`error: ... | hint: ...`), exit code 1.

Keys: $EXA_API_KEY / $CONTEXT7_API_KEY, else ~/.secrets/{exa,context7}-api-key (optional).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SECRETS = Path.home() / ".secrets"
WORK = Path("/tmp") / f"research-{os.environ.get('USER', 'agent')}"
CACHE, OUTDIR = WORK / "cache", WORK / "out"
KEEP_SECONDS = 24 * 3600

ENDPOINTS = {
    "exa": "https://mcp.exa.ai/mcp?tools=web_search_exa,web_search_advanced_exa,web_fetch_exa,get_code_context_exa",
    "c7": "https://mcp.context7.com/mcp",
    "dw": "https://mcp.deepwiki.com/mcp",
    "grep": "https://mcp.grep.app",
}
TTL = {"c7": 24 * 3600, "dw": 24 * 3600, "grep": 6 * 3600, "exa": 3600}
TIMEOUT = {"dw": 240, "exa": 90, "c7": 60, "grep": 60}


class Fail(Exception):
    def __init__(self, msg: str, hint: str = ""):
        super().__init__(msg)
        self.hint = hint


# ----------------------------------------------------------------------------- infra

def api_key(env: str, fname: str) -> str | None:
    if os.environ.get(env):
        return os.environ[env].strip()
    try:
        return (SECRETS / fname).read_text().strip() or None
    except OSError:
        return None


def auth(svc: str) -> dict[str, str]:
    if svc == "exa":
        k = api_key("EXA_API_KEY", "exa-api-key")
        return {"x-api-key": k} if k else {}
    if svc == "c7":
        k = api_key("CONTEXT7_API_KEY", "context7-api-key")
        return {"CONTEXT7_API_KEY": k} if k else {}
    return {}


def sweep() -> None:
    """Delete spilled outputs/cache older than KEEP_SECONDS."""
    cutoff = time.time() - KEEP_SECONDS
    for d in (CACHE, OUTDIR):
        d.mkdir(parents=True, exist_ok=True)
        for p in d.iterdir():
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
            except OSError:
                pass


def _post(svc: str, tool: str, args: dict) -> str:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "User-Agent": "research-cli/2.0", **auth(svc)}
    last: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(ENDPOINTS[svc], body, headers)
            raw = urllib.request.urlopen(req, timeout=TIMEOUT[svc]).read().decode()
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:200].replace("\n", " ")
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                wait = e.headers.get("Retry-After", "")
                time.sleep(min(float(wait) if wait.isdigit() else 2 ** attempt * 1.5, 10))
                last = Fail(f"{tool}: HTTP {e.code} {detail}")
                continue
            hint = {
                401: "key rejected; check ~/.secrets or $EXA_API_KEY/$CONTEXT7_API_KEY",
                403: "blocked; retry later or try another tool",
                429: "rate limited" + ("" if auth(svc) or svc in ("dw", "grep") else " (no API key loaded; keys lift limits)"),
            }.get(e.code, "")
            raise Fail(f"{tool}: HTTP {e.code} {detail}", hint)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = Fail(f"{tool}: {e}", "network/timeout; retry")
            if attempt < 2:
                time.sleep(1.5)
                continue
            raise last
    else:
        raise last or Fail(f"{tool}: failed")
    chunks = [raw] if raw.lstrip().startswith("{") else [l[5:].strip() for l in raw.splitlines() if l.startswith("data:")]
    for c in chunks:
        try:
            d = json.loads(c)
        except ValueError:
            continue
        if d.get("id") != 1:
            continue  # progress / ping notifications
        if "error" in d:
            raise Fail(f"{tool}: {d['error'].get('message')}")
        r = d["result"]
        text = "\n".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text").strip()
        if r.get("isError"):
            raise Fail(f"{tool}: {text[:300]}")
        if not text:
            raise Fail(f"{tool}: empty result", "try a different query")
        return text
    raise Fail(f"{tool}: no response")


def call(svc: str, tool: str, args: dict, fresh: bool = False) -> str:
    key = hashlib.sha1(json.dumps([svc, tool, args], sort_keys=True).encode()).hexdigest()
    path = CACHE / key
    if not fresh and path.exists() and time.time() - path.stat().st_mtime < TTL[svc]:
        return path.read_text()
    text = _post(svc, tool, args)
    path.write_text(text)
    return text


# ----------------------------------------------------------------------------- output

def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "out"


def emit(text: str, a: argparse.Namespace, label: str) -> None:
    """Print inline if small; otherwise preview + full text spilled to a file."""
    text = text.strip()
    if not a.max_chars or len(text) <= a.max_chars:
        print(text)
        return
    cut = text.rfind("\n\n", 0, a.max_chars)
    if cut < a.max_chars * 0.5:
        cut = text.rfind("\n", 0, a.max_chars)
    if cut < a.max_chars * 0.5:
        cut = a.max_chars
    OUTDIR.mkdir(parents=True, exist_ok=True)
    path = OUTDIR / f"{slug(label)}-{hashlib.sha1(text.encode()).hexdigest()[:6]}.md"
    path.write_text(text + "\n")
    lines = text.count("\n") + 1
    print(text[:cut].rstrip())
    print(f"\n[preview {cut:,}/{len(text):,} chars | full output, {lines} lines: {path} | Read with offset/limit, or rg -n]")


# ----------------------------------------------------------------------------- commands

def cmd_docs(a):
    lib = a.library
    if not lib.startswith("/"):
        res = call("c7", "resolve-library-id", {"libraryName": lib, "query": a.query or lib}, a.fresh)
        blocks = [b for b in re.split(r"\n(?=- Title:)", res) if "Context7-compatible library ID:" in b]
        if not blocks:
            raise Fail(f"no library matches '{lib}'", "try a different name, or `web`")

        def field(b, k):
            m = re.search(rf"{k}: *(.*)", b)
            return m.group(1).strip() if m else ""

        if a.list or not a.query:
            for b in blocks[:8]:
                print(f"{field(b, 'Context7-compatible library ID')}  {field(b, 'Title')}  "
                      f"[{field(b, 'Source Reputation')}]  {field(b, 'Description')[:90]}")
            if not a.query:
                print('\n(pass a query to fetch docs: research docs <id> "<question>")')
            return
        lib = field(blocks[0], "Context7-compatible library ID")
        print(f"# context7: {lib}  (wrong library? use --list, then pass its id)")
    res = call("c7", "query-docs", {"libraryId": lib, "query": a.query}, a.fresh)
    if re.match(r'Library ".*" not found', res):
        raise Fail(f"library id '{lib}' not found", "use `research docs <name> --list` to find valid ids")
    emit(res, a, f"docs-{lib}-{a.query}")


def cmd_web(a):
    args: dict = {"query": a.query, "numResults": a.n}
    if any([a.domain, a.exclude, a.after, a.before, a.category]):
        args |= {"textMaxCharacters": a.chars, "enableHighlights": False, "type": "auto"}
        for k, v in (("includeDomains", a.domain), ("excludeDomains", a.exclude),
                     ("startPublishedDate", a.after), ("endPublishedDate", a.before), ("category", a.category)):
            if v:
                args[k] = v
        res = call("exa", "web_search_advanced_exa", args, a.fresh)
        try:
            rows = json.loads(res)["results"]
            res = "\n\n".join(
                f"{(r.get('title') or '').strip()} {r.get('publishedDate') or ''}".strip()
                + f"\n{r['url']}\n{(r.get('text') or '').strip()}" for r in rows) or res
        except (ValueError, KeyError):
            pass
    else:
        args["objective"] = a.objective or a.query
        res = call("exa", "web_search_exa", args, a.fresh)
        res = re.sub(r"^(Title|Published|Author): N/A\n", "", res, flags=re.M)
    emit(res, a, f"web-{a.query}")


def cmd_fetch(a):
    emit(call("exa", "web_fetch_exa", {"urls": a.urls, "maxCharacters": a.chars}, a.fresh), a, f"fetch-{a.urls[0]}")


def cmd_examples(a):
    emit(call("exa", "get_code_context_exa", {"query": a.query, "numResults": a.n}, a.fresh), a, f"examples-{a.query}")


def cmd_wiki(a):
    if a.action == "ask":
        if not a.question:
            raise Fail("wiki ask needs a question", 'research wiki ask owner/repo "<question>"')
        repo = a.repo.split(",") if "," in a.repo else a.repo
        res = call("dw", "ask_wiki_question", {"repoName": repo, "question": a.question}, a.fresh)
    else:
        tool = "read_wiki_structure" if a.action == "outline" else "read_wiki_contents"
        res = call("dw", tool, {"repoName": a.repo}, a.fresh)
    emit(res, a, f"wiki-{a.action}-{a.repo}-{a.question or ''}")


def cmd_code(a):
    args: dict = {"query": a.query}
    for flag, k in ((a.regex, "useRegexp"), (a.case, "matchCase"), (a.word, "matchWholeWords")):
        if flag:
            args[k] = True
    for v, k in ((a.repo, "repo"), (a.path, "path"), (a.lang, "language")):
        if v:
            args[k] = v
    emit(call("grep", "searchGitHub", args, a.fresh), a, f"code-{a.query}")


# ----------------------------------------------------------------------------- cli

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="research", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    def common(parent: argparse.ArgumentParser, d: bool) -> None:
        sup = (lambda v: argparse.SUPPRESS) if d else (lambda v: v)  # subparsers must not override parsed values
        parent.add_argument("--max-chars", type=int, default=sup(6000), help="inline limit before spilling to a file (default 6000, 0=never)")
        parent.add_argument("--fresh", action="store_true", default=sup(False), help="bypass the local cache")

    common(p, False)
    sub = argparse.ArgumentParser(add_help=False)
    common(sub, True)
    s = p.add_subparsers(dest="cmd", required=True, metavar="command")
    add = lambda name, **kw: s.add_parser(name, parents=[sub], **kw)

    d = add("docs", help="library/framework docs (Context7)")
    d.add_argument("library", help="name (react) or Context7 id (/vercel/next.js[/v15.1.0])")
    d.add_argument("query", nargs="?", default="", help="specific question; omit to list candidate ids")
    d.add_argument("--list", action="store_true", help="list candidate ids instead of fetching")
    d.set_defaults(f=cmd_docs)

    w = add("web", help="web search (Exa)")
    w.add_argument("query")
    w.add_argument("-n", type=int, default=5, help="results (default 5)")
    w.add_argument("--objective", help="what you want to learn (improves ranking)")
    w.add_argument("--domain", action="append", help="only this domain (repeatable)")
    w.add_argument("--exclude", action="append", help="exclude domain (repeatable)")
    w.add_argument("--after", metavar="YYYY-MM-DD")
    w.add_argument("--before", metavar="YYYY-MM-DD")
    w.add_argument("--category", choices=["news", "research paper", "github", "company", "pdf", "tweet", "personal site"])
    w.add_argument("--chars", type=int, default=1500, help="text chars per result when filters are used")
    w.set_defaults(f=cmd_web)

    f = add("fetch", help="read page(s) as markdown (Exa)")
    f.add_argument("urls", nargs="+")
    f.add_argument("--chars", type=int, default=20000, help="max chars per page (default 20000)")
    f.set_defaults(f=cmd_fetch)

    e = add("examples", help="code/API usage examples from the web (Exa)")
    e.add_argument("query")
    e.add_argument("-n", type=int, default=3)
    e.set_defaults(f=cmd_examples)

    k = add("wiki", help="OSS repo Q&A and docs (DeepWiki; `ask` can take 10-60s)")
    k.add_argument("action", choices=["ask", "outline", "read"])
    k.add_argument("repo", help="owner/repo (ask: comma-separate up to 5)")
    k.add_argument("question", nargs="?")
    k.set_defaults(f=cmd_wiki)

    g = add("code", help="literal code search across public GitHub (grep.app)")
    g.add_argument("query", help="code as it appears in source; use --regex for patterns")
    g.add_argument("--regex", action="store_true")
    g.add_argument("--case", action="store_true")
    g.add_argument("--word", action="store_true")
    g.add_argument("--repo", help="owner/repo (or prefix) filter")
    g.add_argument("--path", help="file path filter")
    g.add_argument("--lang", action="append", help="language, repeatable (e.g. TypeScript)")
    g.set_defaults(f=cmd_code)

    return p


def main() -> int:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sweep()
    a = parser().parse_args()
    try:
        a.f(a)
    except Fail as e:
        print(f"error: {e}" + (f" | hint: {e.hint}" if e.hint else ""), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
