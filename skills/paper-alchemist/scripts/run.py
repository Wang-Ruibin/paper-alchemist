#!/usr/bin/env python3
"""Codex entrypoint for the bundled runtime or installed Python package."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    if (repo_root / "engine" / "cli.py").is_file():
        # A native plugin must execute its own version, even when an older
        # standalone package is installed in this interpreter.
        sys.path.insert(0, str(repo_root))
        from engine.cli import main as cli_main
    else:
        try:
            from paper_alchemist.cli import main as cli_main
        except ImportError:
            print(
                "Paper Alchemist Python package is missing. Clone the repository and run "
                "`python -m pip install -e .` before using this skill.",
                file=sys.stderr,
            )
            return 2
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
