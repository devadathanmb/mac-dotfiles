# Research

A research skill and CLI for finding documentation, searching the web and public code, and reading pages as Markdown.

## Setup

Requires Python 3.14 or newer. HTTP requests use [HTTPX2](https://pydantic.dev/docs/httpx2/), which verifies TLS with the system trust store and honors `SSL_CERT_FILE` and `SSL_CERT_DIR`.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from this directory:

```sh
uv tool install --editable .
```

This makes `research` available globally. Source changes take effect immediately. If the command isn't found, run `uv tool update-shell` and restart your shell.

Search providers may need API keys. Set the relevant environment variables: `EXA_API_KEY`, `PARALLEL_API_KEY`, `BRAVE_API_KEY`, `TAVILY_API_KEY`, `CONTEXT7_API_KEY`, or `FIRECRAWL_API_KEY`. Direct page fetching works without keys.

## Usage

```sh
research fetch https://example.com
research web "Python asyncio documentation"
research docs httpx2 "How do timeouts work?"
research --help
```

Use `research <command> --help` for command options.

## Tests

Run from this directory:

```sh
uv run python -m unittest discover -s tests
```

## Updating dependencies

After changing dependencies in `pyproject.toml`, run:

```sh
uv lock
uv tool install --editable . --reinstall
```
