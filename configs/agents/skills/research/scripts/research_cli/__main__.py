"""Allow `python -m research_cli`."""

import sys

from .cli import main

sys.exit(main())
