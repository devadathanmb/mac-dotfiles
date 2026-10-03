---
name: research
description: Look up current external info via CLI — library/framework docs (Context7), web search/page fetch (Exa), questions about an open-source repo's internals (DeepWiki), real-world code usage across public GitHub (grep.app). Use when training knowledge may be stale or missing - unfamiliar/new APIs, version-specific behavior, error messages, "how do others do X", repos not available locally. Skip if the local codebase answers it.
---

# research

`python ~/.agents/skills/research/scripts/research.py <cmd>` (written `research` below). Keys load automatically.

| Need | Command |
|---|---|
| Library/framework/SDK docs | `research docs <name or /org/repo[/ver]> "<specific question>"` |
| Web: articles, issues, changelogs, errors | `research web "<query>"`, then `research fetch <url>` |
| API usage snippets (docs, blogs, SO) | `research examples "<query>"` |
| How an OSS repo works internally | `research wiki ask owner/repo "<question>"` |
| Literal code patterns in real repos | `research code "<snippet>" [--lang L] [--repo R]` |

"How do I use X": `docs` → `examples` → `code`. Anything not documentation: `web`.

## Output

- Small results print inline. Large ones end with `[preview N/M chars | full output, L lines: <path> | ...]`: the preview is usually enough; otherwise `rg -n` or Read with offset/limit on `<path>`. Don't re-run with a bigger cap.
- Errors: `error: ... | hint: ...` on stderr, exit 1. Follow the hint, or fall back to another command.
- Results are cached locally; `--fresh` bypasses.

## Method

- Scale effort to the question: a lookup is 1–3 calls to the most authoritative source; a comparison or decision needs several sources, then narrow to the claims the answer depends on. Stop once primary sources confirm it; state remaining uncertainty.
- Exact details (flags, defaults, limits, versions) need raw text: summaries drop them. `fetch` the raw page (`.md` docs, `llms.txt`, `raw.githubusercontent.com`) and `rg` it.
- Note each source's date and the version it describes; flag anything older than a relevant release.
- Rank sources: official docs / source / changelogs > maintainer comments in issues and PRs > independent blogs > aggregators. Confirm surprising claims with a second source and state conflicts.
- Verify anything that may have changed (API behavior, versions, pricing, limits) instead of answering from memory. If tools fail, say which were tried and mark the answer unverified.
- Fallbacks if a command fails: `gh` (issues, releases, repo files), PyPI/npm metadata, or a shallow clone in a temp dir searched with `rg`.
- Research answers: lead with the answer, separate confirmed from inferred, stamp version/time-sensitive claims ("as of v2.3"), and end with `## Sources` listing only what you actually read (tool + URL or repo).

## Slow calls

`wiki ask` takes 10–60s (up to 4 min). Run it with your harness's background-task feature if available; otherwise run it foreground with a shell timeout ≥ 240s.

## Options

```
docs <lib> "<q>"      lib auto-resolves to top match (id shown on first line); wrong one? `docs <lib> --list`, then pass its /org/repo
web "<q>" [-n 5] [--objective "..."] [--domain D]... [--exclude D]... [--after|--before YYYY-MM-DD] [--category news|github|research paper|pdf|company|tweet|personal site]
fetch <url>... [--chars 20000]
examples "<q>" [-n 3]
wiki ask owner/repo[,owner/repo2] "<q>" | wiki outline owner/repo | wiki read owner/repo (whole wiki, huge)
code "<literal snippet>" [--regex] [--case] [--word] [--repo owner/repo] [--path P] [--lang TypeScript]...
any command: --max-chars N (inline limit, default 6000)  --fresh
```

## Tips

- `docs`: name the symbol in the query ("useOptimistic reducer signature"), not just the library.
- `web`: search first, `fetch` only the 1–2 URLs that matter; `--domain`/`--after` cut noise.
- `code`: query is literal source text (`useOptimistic(`), not a description.
- `wiki ask` is AI-generated; verify critical details in source.
