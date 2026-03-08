---
name: good-comments
description: Use when writing or refactoring comments or docstrings in any language, adding documentation, or reviewing comment quality - applies "Art of Readable Code" principles to write comments that explain WHY not WHAT, use markers for flaws (TODO/FIXME/HACK), anticipate reader questions, record decision rationale, and avoid redundant documentation. All examples use Python, but every principle is language-agnostic - adapt docstring conventions to your language's idiomatic equivalent.
---

# Writing Good Comments

> All examples use Python. The principles apply to every language — adapt the docstring/documentation syntax to whatever you're working in.

**Core principle:** Good code > bad code + comments. Comments explain WHY, not WHAT. Help readers know what you knew when writing code.

## What TO Comment

| Type | Example |
|------|---------|
| **Decision rationale** | `# Using binary search: data sorted from DB, 2x faster than hash (benchmarked)` |
| **Flaws** | `TODO: Add caching after 10k users`<br>`FIXME: Race condition with threads`<br>`HACK: Hardcoded limit; need backoff` |
| **Constants** | `TIMEOUT = 30  # 95th percentile (22s) + 8s buffer from production data` |
| **Anticipated questions** | `# Counterintuitive: lower is better (golf scoring)`<br>`# Why not success_rate? A/B test showed no value` |
| **Warnings** | `"""WARNING: Blocks 5s. Call from background worker only."""` |
| **Edge cases** | `>>> parse("yesterday")  # Returns same date for start/end` |
| **High-level story** | `"""Auth flow: credentials → JWT → Redis session → token"""` |
| **Code paragraphs** | `# Phase 1: Validate transactions` (if >15 lines, extract function instead) |

## What NOT to Comment

- Facts derived from code: ~~`# Check if adult`~~ → `# Legal age varies; 18 is US standard`
- Bad names: ~~`def process(d)`~~ → Rename to `double_price(price_usd)`
- Obvious details, history (use git), commented-out code (delete it)

## Docstring / Doc-Comment Structure (Python: Google Style)

```python
def calculate(point_a, point_b, metric='euclidean'):
    """Calculate distance between points.

    Args:
        point_a (tuple): First point (x, y).
        metric (str, optional): 'euclidean', 'manhattan'. Defaults to 'euclidean'.

    Returns:
        float: Distance between points.

    Raises:
        ValueError: If metric not recognized.

    Examples:
        >>> calculate((0, 0), (3, 4))
        5.0
    """
```

**Class:** `"""Brief description.\n\nAttributes:\n    attr (type): Description."""`

**Module:** `"""Brief description.\n\nTypical usage:\n    from module import func"""`

## Workflow

1. **Remove** - obvious/outdated comments, commented-out code
2. **Refactor code** - descriptive names, extract functions
3. **Add strategic comments** - WHY decisions, warnings, markers
4. **Write doc-comments** - Use your language's idiomatic style for public APIs (Google style in Python)

## Red Flags

- Commenting every line → Only comment non-obvious code
- Restating variable names → Delete or explain WHY
- Explaining WHAT not WHY → Fix code or explain decision

## Checklist

**Remove:** restating comments, bad names (rename), commented-out code, outdated comments

**Add:** WHY for decisions, markers (TODO/FIXME/HACK), constant reasoning, warnings, examples, idiomatic doc-comments for public APIs
