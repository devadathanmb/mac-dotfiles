# Research

A research skill and CLI for AI agents: library docs, web search, page reading, and public code search, with output sized for an agent's context.

## Setup

Requires Python 3.14. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from this directory:

```sh
uv tool install --python 3.14 --editable .
```

This makes `research` available globally; source changes take effect immediately. If the command isn't found, run `uv tool update-shell` and restart your shell.

Search providers may need API keys, read from the environment or from a file of the same name in `~/.secrets`: `EXA_API_KEY` (`exa-api-key`), `PARALLEL_API_KEY`, `BRAVE_API_KEY`, `TAVILY_API_KEY`, `CONTEXT7_API_KEY`, `FIRECRAWL_API_KEY`, and optionally `STACKEXCHANGE_KEY` (raises the Stack Exchange quota from 300 to 10,000 requests a day). GitHub requests use `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`. Page fetching works without keys.

## Usage

```sh
research fetch https://example.com
research web "Python asyncio documentation"
research docs httpx2 "How do timeouts work?"
research --help
```

`research <command> --help` lists each command's options. `SKILL.md` teaches agents when and how to use them.

## How pages are fetched

1. **Site APIs** answer URLs they have a better copy of: Stack Exchange questions and answers, GitHub issues, pull requests, and `blob` files.
2. **Browser fingerprint:** [curl_cffi](https://curl-cffi.readthedocs.io/) impersonates Chrome's TLS and HTTP/2 handshake, which bot protection checks. It still sends `Accept: text/markdown` first, so sites that serve markdown to agents (Cloudflare docs, GitHub docs) do.
3. **Plain client:** [HTTPX2](https://pydantic.dev/docs/httpx2/) retries when the browser fingerprint is refused (some sites block it), or when TLS fails: curl_cffi reads `SSL_CERT_FILE`, Python's CA file, or certifi, while HTTPX2 also trusts the macOS keychain, where corporate proxy roots live.
4. **Exa**, then **Firecrawl** (with a key), when the page is blocked, a bot challenge, a sign-in redirect, or rendered by JavaScript.

A 404 stops the chain. Bodies are capped at 10 MiB after decompression (gzip, deflate, and Zstandard; Brotli too in the browser client). API calls (search providers, MCP servers, GitHub, Stack Exchange) use HTTPX2.

## Layout

| Module | Role |
| --- | --- |
| `cli.py` | Parser and validation; builds each command's typed options |
| `commands/` | One module per subcommand |
| `transport.py` | The browser and plain HTTP clients, size caps, error mapping |
| `fetching.py` | The fallback chain and the concurrent batch runner |
| `pages.py`, `extract.py` | Direct reads and HTML-to-markdown conversion |
| `github.py`, `stackexchange.py` | Site API adapters |
| `providers.py`, `search.py`, `layout.py` | Search providers, rank fusion, result layout |
| `mcp.py`, `firecrawl.py` | Hosted MCP servers and Firecrawl |
| `excerpts.py`, `output.py` | Outlines, selectors, previews, and saved files |
| `cache.py`, `config.py`, `credentials.py` | Cache, limits and timeouts, keys |

## Development

Run from this directory:

```sh
uv run python -m unittest discover -s tests   # tests; no network access
uv run ruff format . && uv run ruff check .   # format and lint
uv run pyright                                 # type check
```

Tests run the real CLI against a fake web (`tests/support.py`); `tests/test_transport.py` exercises the real curl_cffi and HTTPX2 clients against a local server.

After changing dependencies in `pyproject.toml`, run:

```sh
uv lock
uv tool install --python 3.14 --editable . --reinstall
```
