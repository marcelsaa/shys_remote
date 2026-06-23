"""CLI entry points for building the bundled Flipper-IRDB index."""

from __future__ import annotations

from .irdb_catalog import build_index_from_github, paths_from_entries

__all__ = ["build_index_from_github", "paths_from_entries"]
