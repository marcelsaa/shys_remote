#!/usr/bin/env python3
"""Build the bundled Flipper-IRDB search index for shys_remote.

Run this when preparing a release or after updating the Flipper-IRDB snapshot.

Examples:
  python build_irdb_index.py --from-storage ../../../../.storage/shys_ir_remote_irdb_index_v2
  python build_irdb_index.py --from-github
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_DIR = SCRIPT_DIR.parent
OUTPUT_PATH = COMPONENT_DIR / "data" / "irdb_index.json"

if str(COMPONENT_DIR) not in sys.path:
    sys.path.insert(0, str(COMPONENT_DIR))

from irdb_catalog import build_index_from_github, paths_from_entries


def _load_storage_paths(storage_path: Path) -> list[str]:
    """Extract remote paths from a Home Assistant storage file."""
    payload = json.loads(storage_path.read_text(encoding="utf-8"))
    data = payload.get("data", payload)
    entries = data.get("entries", [])
    paths: list[str] = []
    for entry in entries:
        if isinstance(entry, dict):
            path = entry.get("path")
            if isinstance(path, str) and path:
                paths.append(path)
        elif isinstance(entry, str) and entry:
            paths.append(entry)
    return sorted(set(paths))


def _write_index(paths: list[str], *, source: str) -> None:
    """Write the bundled index file."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "path_count": len(paths),
        "paths": paths,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(paths)} paths to {OUTPUT_PATH}")


def main() -> int:
    """Build the bundled IRDB index."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--from-storage",
        type=Path,
        metavar="PATH",
        help="Read paths from a Home Assistant .storage index file",
    )
    source.add_argument(
        "--from-github",
        action="store_true",
        help="Download and curate the index from Flipper-IRDB on GitHub",
    )
    args = parser.parse_args()

    if args.from_storage:
        if not args.from_storage.is_file():
            print(f"Storage file not found: {args.from_storage}", file=sys.stderr)
            return 1
        paths = _load_storage_paths(args.from_storage)
        source_label = f"storage:{args.from_storage.name}"
    else:
        entries = asyncio.run(build_index_from_github())
        paths = paths_from_entries(entries)
        source_label = "github:Lucaslhm/Flipper-IRDB@main"

    if not paths:
        print("No index paths generated.", file=sys.stderr)
        return 1

    _write_index(paths, source=source_label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
