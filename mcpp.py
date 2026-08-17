#!/usr/bin/env python3
"""Hermetic ``python -m mcpp`` bootstrap for McppCli@1 (MCPP-075).

The installable implementation is the declared output ``cli/mcpp.py`` (mapped
to the ``mcpp`` module by setuptools ``package-dir``).  This root module only
exists so validation can run ``cd …/mcplusplus && python -m mcpp doctor`` with
the package root on ``sys.path`` and without a prior editable install.
"""

from __future__ import annotations

from cli.mcpp import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(int(main()))
