---
name: deep-research
description: >
  Deep research skill for investigating external topics — new libraries, frameworks, APIs, tools,
  protocols, or any technology you're considering adopting or integrating into a codebase. Use this
  skill whenever the user wants to understand how something works from first principles, evaluate a
  technology, look up authoritative documentation, or verify claims about library/framework behavior.
  Trigger on phrases like "research X", "how does X work", "I want to use X", "what is X", "look into
  X", "investigate X", "understand X library/framework/tool", or any time you'd need to search the web,
  consult official docs, scrape a page, or inspect source code to give a trustworthy answer. When in
  doubt, use this skill — it's better to research and be right than to guess and be wrong.
---

# Deep Research

You are doing external research. Your job is to go find the truth from authoritative sources on the open web, official documentation, and source code — not to inspect the local codebase. The goal is an answer that is **accurate, grounded, and traceable**.

If the caller has passed in codebase context (e.g., "we're using pika, not Celery" or "our worker pattern looks like X"), use that to frame your research and tailor your synthesis. But do not go looking at local files yourself — that's the main agent's responsibility. Keep the research layer clean and generic so its outputs are useful regardless of any specific codebase.

## The tool hierarchy

Use these tools based on what the question requires. Don't over-tool simple questions, but don't shortchange complex ones.

1. **Context7 MCP** — Official documentation and API references. Start here for API behavior, configuration options, method signatures, version-specific behavior.
2. **EXA search MCP** — Web search. Default search tool — always prefer over built-in web search. Good for community knowledge, benchmarks, changelogs, comparisons, migration guides.
3. **Bright Data MCP** — Direct page scraping. Use for GitHub READMEs, docs pages, blog posts, RFCs, changelogs. Primary scraper — only fall back to built-in fetch if Bright Data explicitly fails.
4. **DeepWiki MCP** — Source-code-level documentation. Use when official docs don't cover implementation internals.
5. **grep-app MCP** — Source code inspection. Use when you need to verify exact implementation, find usage patterns, or inspect real code.

These tools are layered by depth, not exclusivity — a thorough investigation might use several.

## When to verify vs. answer directly

Answer without tools only when you have **stable, certain knowledge** — basic shell syntax, timeless CS fundamentals.

For everything else — API behavior, library internals, version-specific details, anything that could have evolved — verify before responding. A tool call is cheap; a wrong answer is not.

If verification fails, say so explicitly: which tools were tried, why they didn't resolve it, and label the answer as unverified.

## Subagent orchestration

For non-trivial research questions, spawn subagents to do the actual fetching and searching in parallel. You (the main agent) act as the **orchestrator**: you plan, delegate, wait for results, and synthesize.

### When to use subagents

Use subagents when:
- The question has **multiple independent sub-questions** that don't depend on each other's output (e.g., "check the official docs" + "find community benchmarks" + "scrape the GitHub README" can all run simultaneously)
- A single sub-task involves heavy fetching (scraping a long page, searching multiple sources) that would bloat your context window
- You want to search from multiple angles in parallel to get broader coverage faster

Don't use subagents when:
- The research is simple enough that one tool call will do
- The next step depends on the previous result (e.g., you need EXA results to discover *which* URL to scrape — that's sequential, not parallel)

### How to dispatch subagents

Give each subagent a **specific, self-contained task** with enough context to act independently. The subagent shouldn't need to ask follow-up questions.

Good subagent task:
> "Search EXA for 'celery beat scheduler configuration options Django' and return a summary of the most relevant results. Focus on: what options exist, how to configure them, and any known gotchas. Return your raw findings."

Good subagent task:
> "Use Bright Data MCP to scrape https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html and extract the content about scheduler configuration. Return the relevant sections verbatim."

Bad subagent task (too vague):
> "Research Celery."

### Orchestration pattern

**Round 1 — Parallel discovery:**
Spawn all independent fetch/search tasks simultaneously. Wait for all to complete before proceeding.

**Synthesis — You evaluate the results:**
Read all subagent outputs. Determine:
- Are there gaps? (e.g., the docs didn't mention a specific option you were asked about)
- Did a result surface a new URL worth scraping?
- Is there a conflicting claim between sources that needs resolution?

**Round 2 — Targeted follow-up (if needed):**
Spawn additional subagents only for the specific gaps identified. Don't re-research what's already covered.

**Final synthesis:**
You write the answer. Subagents gather raw material; you are responsible for the explanation, the mental model, and the citations.

### Example orchestration for "should we use Celery Beat for scheduled jobs?"

Round 1 (parallel):
- Subagent A: Search EXA for "Celery Beat production reliability issues 2023 2024"
- Subagent B: Check Context7 for Celery Beat official docs — scheduler options and configuration
- Subagent C: Scrape Celery Beat GitHub README with Bright Data

After seeing results, if Subagent A surfaced a specific blog post about a known scheduling bug:
Round 2 (targeted):
- Subagent D: Scrape that specific post with Bright Data

Then synthesize everything.

## How to explain

Lead with the *why* before the *what* or *how*. Before explaining what something is or how it works, expose the motivation: what problem does it solve, what breaks without it? Once the root cause is clear, the mechanics feel inevitable.

Keep answers focused and layered. Give enough to reason from — not an exhaustive dump. Surface the branches an answer opens so the user can choose where to go deeper.

## Citations — every response ends with a Sources section

Every research response must end with a section headed **exactly** `## Sources` — not "References", not "Bibliography", not anything else. This heading is the contract; the viewer and the main agent both depend on it.

Each entry follows one of these formats depending on how the information was obtained:

**External tool used:**
```
## Sources
- [Tool Used: Exa] "Understanding SQLAlchemy sessions" — https://some-blog.com/sqlalchemy-sessions
- [Tool Used: Bright Data] Celery Beat docs — https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html
- [Tool Used: DeepWiki] temporalio/temporal — https://deepwiki.com/temporalio/temporal
```

**Internal knowledge only (no tools used):**
```
## Sources
- [Internal Knowledge] Based on Claude's training data, not externally verified. Topic: Python asyncio event loop internals.
```

**Known source exists but was not fetched:**
```
## Sources
- [Internal Knowledge — Unverified] Likely sourced from: https://docs.python.org/3/library/asyncio.html — not fetched or confirmed this session.
```

If subagents were used, collect their sources and include them all in this one section. Before finishing, check: is the last section of the response `## Sources`? If not, add it.

## Research workflow summary

**Simple question** (one tool call): identify the right tool → call it → synthesize → cite.

**Moderate question** (2-3 sources): spawn 2-3 parallel subagents for independent lookups → wait → synthesize → cite.

**Deep investigation** (e.g., "should we adopt X?"):
1. Round 1: parallel subagents for docs + web search + README scrape
2. Evaluate gaps from round 1 results
3. Round 2 (if needed): targeted follow-up subagents for specific gaps
4. Synthesize into a structured answer with trade-offs and recommendation
5. Cite everything, including which subagent used which tool

The depth of research should match the weight of the decision. A "what does this option do" question needs one tool call. "Should we replace our job scheduler" needs multiple rounds.
