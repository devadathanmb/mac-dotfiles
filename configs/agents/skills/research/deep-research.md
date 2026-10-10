# Deep research

Use this for questions one lookup cannot settle: comparisons, feasibility, "what is the current state of X", root causes that span projects, or claims that sources dispute. A single fact still takes one command from `SKILL.md`.

## Procedure

1. **Decompose.** Write the 3–6 sub-questions whose answers decide the outcome, and for each the kind of source that would be authoritative (official docs, source code, changelog, maintainer comment, benchmark, paper).
2. **Fan out once.** One `web` call with a query per sub-question, `--backend all`, and `--read 3`:
   `research web "<q1>" "<q2>" "<q3>" --backend all --read 3 --max-chars 8000`
   Results and the pages read alternate between queries, so give each sub-question its own query. Expect 8–15 seconds; allow for that in the command timeout. A result tagged with one provider is not weaker evidence, only a less corroborated lead. A `[provider (query N) failed]` notice means that provider was skipped for that query, not that the search failed.
3. **Read the decisive pages, selectively.** `fetch` the primary sources among the leads in one batch with `--query "<sub-question>"`. Batch pages that answer the same sub-question; a shared `--query` across unrelated pages selects poorly. Use `--section` once an outline shows where the answer lives. For GitHub issues and pull requests, read the saved file to the end: the decisive maintainer comment is often last.
4. **Chase what is still open.** For each sub-question without a primary source, run a narrower query: the exact error string or symbol (`--backend brave`), a `--domain` restricted to the project's docs or repo, `code` for the implementation, `wiki ask` for architecture. Stop a line of inquiry after two misses and record it as unresolved.
5. **Try to break the answer.** Search once for the opposite claim ("X does not support Y", "X deprecated", "X regression"). Check dates and versions on everything decisive; a correct statement about an older release is a wrong answer.
6. **Answer.** Per sub-question: the finding, the source you read, and its version or date. List conflicts between sources and what you could not verify.

## Rules

- Keep sources in files, not in context: saved paths persist for 24 hours, so reread a passage with `rg` or Read at the cited lines instead of fetching again.
- Run independent `web`/`fetch`/`code` calls in parallel; run `wiki ask` in the background while they finish.
- Every decisive claim needs a page you read, not a search snippet. Snippets are leads.
- Two independent primary sources outweigh any number of pages repeating each other; pages citing the same origin count once.
- For a miss, say "not found in <sources searched>", never "does not exist".
- Budget: about 10–15 calls. If the answer is still open, report what is established and what is missing rather than continuing to search.
