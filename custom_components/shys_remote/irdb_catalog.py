"""Flipper-IRDB path parsing and offline index building (no Home Assistant dependency)."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import aiohttp

IRDB_REPO = "Lucaslhm/Flipper-IRDB"
IRDB_BRANCH = "main"
IRDB_TREE_URL = (
    f"https://api.github.com/repos/{IRDB_REPO}/git/trees/{IRDB_BRANCH}?recursive=1"
)
IRDB_ROOT_URL = f"https://api.github.com/repos/{IRDB_REPO}/contents/?ref={IRDB_BRANCH}"
IRDB_CATEGORY_TREE_URL = (
    f"https://api.github.com/repos/{IRDB_REPO}/git/trees/{{sha}}?recursive=1"
)
IRDB_RAW_URL = f"https://raw.githubusercontent.com/{IRDB_REPO}/{IRDB_BRANCH}/{{path}}"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=300)
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "shys_remote-index-builder",
}

EXCLUDED_ROOT_FOLDERS = frozenset(
    {
        "_converted_",
        "csv",
        ".github",
    }
)
JUNK_PATH_MARKERS = ("/_converted_/", "/_converted_.ir")
JUNK_SEGMENT_NAMES = frozenset({"converted", "_converted_", "csv"})
COORDINATE_SEGMENT = re.compile(r"^-?\d+,-?\d+$")

BUNDLED_INDEX_VERSION = 1
BUNDLED_INDEX_FILENAME = "irdb_index.json"


def _humanize_segment(segment: str) -> str:
    """Turn a path segment into readable text."""
    text = segment
    if text.lower().endswith(".ir"):
        text = text[:-3]
    return text.replace("_", " ").strip()


def _is_junk_segment(segment: str) -> bool:
    """Return whether a path segment is bulk-import noise."""
    text = segment.lower()
    if not text:
        return True
    if text in JUNK_SEGMENT_NAMES:
        return True
    if COORDINATE_SEGMENT.fullmatch(text):
        return True
    humanized = _humanize_segment(segment).lower()
    if humanized in JUNK_SEGMENT_NAMES:
        return True
    cleaned = humanized.replace(",", "").replace(".", "").replace("-", "").replace(" ", "")
    return bool(cleaned.isdigit())


def _is_excluded_root(path: str) -> bool:
    """Return whether a repository path belongs to an excluded top-level folder."""
    parts = [part for part in path.split("/") if part]
    if not parts:
        return True
    root = parts[0].lower()
    if root in EXCLUDED_ROOT_FOLDERS:
        return True
    return "converted" in root or root == "csv"


def _is_excluded_category(name: str) -> bool:
    """Return whether a top-level category should be skipped."""
    lower = name.lower()
    if lower in EXCLUDED_ROOT_FOLDERS:
        return True
    return "converted" in lower or lower == "csv"


def _is_quality_entry(path: str, brand: str, model: str) -> bool:
    """Return whether an index entry is a curated remote, not bulk-import noise."""
    parts = [part for part in path.split("/") if part]
    if len(parts) < 3:
        return False
    if _is_excluded_root(path):
        return False
    if any(_is_junk_segment(part) for part in parts):
        return False
    if _is_junk_segment(brand) or _is_junk_segment(model):
        return False
    return True


def _should_index_path(path: str) -> bool:
    """Return whether a repository path should appear in the search index."""
    lower = path.lower()
    if not lower.endswith(".ir"):
        return False
    if lower.startswith(".") or "/." in lower:
        return False
    if any(marker in lower for marker in JUNK_PATH_MARKERS):
        return False
    if _is_excluded_root(path):
        return False

    parts = [part for part in path.split("/") if part]
    if len(parts) < 3:
        return False

    brand = parts[1] if len(parts) > 1 else ""
    model = parts[-1][:-3] if parts[-1].lower().endswith(".ir") else parts[-1]
    return _is_quality_entry(path, brand, model)


def _strip_brand_prefix(brand: str, model: str) -> str:
    """Remove a duplicated brand prefix from a model filename."""
    if not brand:
        return model

    brand_lower = brand.lower()
    model_lower = model.lower()
    prefix = f"{brand_lower}_"
    if model_lower.startswith(prefix):
        return model[len(prefix) :]
    if model_lower.startswith(brand_lower):
        return model[len(brand) :].lstrip("_")
    return model


def _build_entry_label(directories: list[str], model: str) -> str:
    """Build a human-readable label following the Flipper-IRDB layout."""
    device_type = directories[0] if directories else ""
    brand = directories[1] if len(directories) > 1 else ""
    subpath = directories[2:] if len(directories) > 2 else []

    brand_h = _humanize_segment(brand)
    model_h = _humanize_segment(_strip_brand_prefix(brand, model))
    device_h = _humanize_segment(device_type)
    subpath_h = [_humanize_segment(part) for part in subpath]

    if brand_h and model_h:
        label = f"{brand_h} {model_h}"
    elif model_h:
        label = model_h
    elif brand_h:
        label = brand_h
    else:
        label = device_h or model

    if subpath_h:
        label = f"{label} ({' / '.join(subpath_h)})"
    if device_h:
        label = f"{label} · {device_h}"
    return label


def parse_tree_path(path: str) -> dict[str, str] | None:
    """Parse a repository path into a curated index entry."""
    if not _should_index_path(path):
        return None

    parts = [part for part in path.split("/") if part]
    filename = parts[-1]
    directories = parts[:-1]
    model = filename[:-3] if filename.lower().endswith(".ir") else filename

    device_type = directories[0]
    brand = directories[1] if len(directories) > 1 else ""
    label = _build_entry_label(directories, model)
    search_text = " ".join(part.lower().replace("_", " ") for part in parts)

    return {
        "path": path,
        "device_type": device_type,
        "brand": brand,
        "model": model,
        "label": label,
        "search_text": search_text,
    }


def entries_from_paths(paths: list[str]) -> list[dict[str, str]]:
    """Build curated index entries from repository paths."""
    entries: list[dict[str, str]] = []
    for path in paths:
        parsed = parse_tree_path(path)
        if parsed is not None:
            entries.append(parsed)
    entries.sort(key=lambda entry: (entry["label"].lower(), entry["path"].lower()))
    return entries


def sanitize_index_entries(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    """Re-validate cached entries and drop legacy bulk-import noise."""
    return entries_from_paths([entry.get("path", "") for entry in entries])


def entries_from_tree_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Parse a GitHub tree payload into curated index entries."""
    paths: list[str] = []
    for item in payload.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        if path and not _is_excluded_root(path):
            paths.append(path)
    return entries_from_paths(paths)


def merge_entries(*entry_lists: list[dict[str, str]]) -> list[dict[str, str]]:
    """Merge index entry lists by path."""
    merged: dict[str, dict[str, str]] = {}
    for entries in entry_lists:
        for entry in entries:
            merged[entry["path"]] = entry
    result = list(merged.values())
    result.sort(key=lambda entry: (entry["label"].lower(), entry["path"].lower()))
    return result


async def _fetch_json(session: aiohttp.ClientSession, url: str) -> Any:
    """Fetch JSON from GitHub."""
    async with session.get(url, timeout=REQUEST_TIMEOUT, headers=GITHUB_HEADERS) as response:
        if response.status == 403:
            raise RuntimeError("GitHub API rate limit reached")
        if response.status != 200:
            raise RuntimeError(f"GitHub request failed with HTTP {response.status}")
        return await response.json()


async def _build_index_from_categories(
    session: aiohttp.ClientSession,
) -> list[dict[str, str]]:
    """Build the index by fetching each top-level category separately."""
    root_items = await _fetch_json(session, IRDB_ROOT_URL)
    categories = [
        item
        for item in root_items
        if item.get("type") == "dir"
        and not item.get("name", "").startswith(".")
        and not _is_excluded_category(item.get("name", ""))
    ]

    entries: list[dict[str, str]] = []
    for category in categories:
        category_name = category.get("name", "")
        tree_sha = category.get("sha", "")
        if not category_name or not tree_sha:
            continue
        payload = await _fetch_json(
            session, IRDB_CATEGORY_TREE_URL.format(sha=tree_sha)
        )
        for item in payload.get("tree", []):
            if item.get("type") != "blob":
                continue
            relative_path = item.get("path", "")
            if not relative_path:
                continue
            full_path = f"{category_name}/{relative_path}"
            parsed = parse_tree_path(full_path)
            if parsed is not None:
                entries.append(parsed)
        await asyncio.sleep(0.5)

    entries.sort(key=lambda entry: (entry["label"].lower(), entry["path"].lower()))
    return entries


async def build_index_from_github() -> list[dict[str, str]]:
    """Download and curate the Flipper-IRDB search index from GitHub."""
    async with aiohttp.ClientSession() as session:
        payload = await _fetch_json(session, IRDB_TREE_URL)
        full_tree_entries = entries_from_tree_payload(payload)
        if full_tree_entries and not payload.get("truncated"):
            return full_tree_entries

        category_entries = await _build_index_from_categories(session)
        entries = merge_entries(full_tree_entries, category_entries)
        if not entries:
            raise RuntimeError("Flipper-IRDB index build returned no entries")
        return entries


def paths_from_entries(entries: list[dict[str, str]]) -> list[str]:
    """Return sorted unique paths from curated index entries."""
    return sorted({entry["path"] for entry in entries if entry.get("path")})
