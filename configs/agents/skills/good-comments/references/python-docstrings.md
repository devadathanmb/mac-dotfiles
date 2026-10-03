# Python Docstring Format

Use this reference only after `SKILL.md` establishes that a docstring carries a necessary contract.

## One-line Docstring

Keep the closing quotes on the same line. Use an imperative summary and a final period.

```python
def count_lines(path: str) -> int:
    """Count `\n` bytes; ignore standalone carriage returns."""
```

## Multi-line Docstring

Put the summary on the first line, add a blank line, then include only sections that carry information absent from the signature.

```python
def fetch_page(
    page: int,
    *,
    timeout_seconds: float | None = None,
) -> list[Record]:
    """Fetch one page from the vendor records API.

    Args:
        page: One-based page number required by the vendor.
        timeout_seconds: Request timeout; `None` uses the client default.

    Returns:
        Records in vendor response order.

    Raises:
        TimeoutError: The vendor does not respond before the timeout.

    Note:
        This call is not retried because the vendor bills each request.
    """
```

Type hints carry types; docstrings carry semantics, constraints, side effects, and failure behavior. With complete hints and an obvious contract, omit the docstring.

## Style

Use Google-style sections for structured docstrings. Do not copy inconsistent local formats.
