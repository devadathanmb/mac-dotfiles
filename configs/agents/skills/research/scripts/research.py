#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.28,<1", "html-to-markdown>=3,<4", "selectolax>=0.4,<1"]
# ///
"""Research docs, web pages, repositories, and public code."""

import sys

from research_cli.cli import main

if __name__ == "__main__":
    sys.exit(main())
