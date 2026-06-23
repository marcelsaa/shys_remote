"""Flipper-IRDB search and remote download."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LEGACY_IRDB_INDEX_STORE_KEY
from .irdb_catalog import (
    BUNDLED_INDEX_FILENAME,
    BUNDLED_INDEX_VERSION,
    IRDB_RAW_URL,
    REQUEST_TIMEOUT,
    entries_from_paths,
    sanitize_index_entries,
)

_LOGGER = logging.getLogger(__name__)

LEGACY_INDEX_STORE_KEYS = (
    f"{DOMAIN}_irdb_index_v2",
    LEGACY_IRDB_INDEX_STORE_KEY,
)


class IrdbClient:
    """Search and download remotes from Flipper-IRDB."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the IRDB client."""
        self.hass = hass
        self._entry = entry
        self._entries: list[dict[str, str]] | None = None
        self._bundled_path = Path(__file__).with_name("data") / BUNDLED_INDEX_FILENAME

    def _read_json_file(self, path: Path) -> dict[str, Any] | None:
        """Read a JSON file from disk."""
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            _LOGGER.debug("Could not read IRDB index file %s: %s", path, err)
            return None
        return payload if isinstance(payload, dict) else None

    def _entries_from_bundled_file(self) -> list[dict[str, str]] | None:
        """Load the bundled Flipper-IRDB index shipped with the integration."""
        payload = self._read_json_file(self._bundled_path)
        if not payload:
            return None

        paths: list[str] = []
        if isinstance(payload.get("paths"), list):
            paths = [path for path in payload["paths"] if isinstance(path, str)]
        elif isinstance(payload.get("entries"), list):
            for entry in payload["entries"]:
                if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                    paths.append(entry["path"])

        entries = entries_from_paths(paths)
        if not entries:
            return None

        _LOGGER.debug(
            "Loaded bundled Flipper-IRDB index v%s with %s remotes from %s",
            payload.get("version", "?"),
            len(entries),
            self._bundled_path.name,
        )
        return entries

    def _write_bundled_index(
        self, entries: list[dict[str, str]], *, source: str
    ) -> None:
        """Persist a curated path list for future loads and releases."""
        paths = sorted({entry["path"] for entry in entries})
        payload = {
            "version": BUNDLED_INDEX_VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "path_count": len(paths),
            "paths": paths,
        }
        try:
            self._bundled_path.parent.mkdir(parents=True, exist_ok=True)
            self._bundled_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as err:
            _LOGGER.warning(
                "Could not write bundled IRDB index to %s: %s",
                self._bundled_path,
                err,
            )
            return

        _LOGGER.info(
            "Wrote bundled Flipper-IRDB index with %s remotes to %s",
            len(paths),
            self._bundled_path,
        )

    def _entries_from_legacy_storage(self) -> list[dict[str, str]] | None:
        """Load a legacy Home Assistant storage index as a one-time fallback."""
        for store_key in LEGACY_INDEX_STORE_KEYS:
            path = Path(self.hass.config.path(".storage", store_key))
            payload = self._read_json_file(path)
            if not payload:
                continue

            data = payload.get("data", payload)
            raw_entries = data.get("entries") if isinstance(data, dict) else None
            if not isinstance(raw_entries, list):
                continue

            entries = sanitize_index_entries(raw_entries)
            if not entries:
                continue

            _LOGGER.info(
                "Loaded legacy IRDB storage fallback with %s remotes from %s",
                len(entries),
                path.name,
            )
            return entries

        return None

    def _load_index_entries(self) -> list[dict[str, str]]:
        """Load the local Flipper-IRDB search index."""
        bundled = self._entries_from_bundled_file()
        if bundled is not None:
            return bundled

        legacy = self._entries_from_legacy_storage()
        if legacy is not None:
            self._write_bundled_index(legacy, source="legacy:storage")
            return legacy

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="irdb_index_failed",
            translation_placeholders={"status": "missing"},
        )

    @staticmethod
    def _term_matches_entry(entry: dict[str, str], term: str) -> bool:
        """Return whether a term matches the brand, model or brand folder in the path."""
        brand = entry["brand"].lower().replace("_", " ")
        model = entry["model"].lower().replace("_", " ")
        path = entry["path"].lower()

        if term == brand or brand.startswith(term) or term in brand:
            return True
        if term in model or model.startswith(term):
            return True
        if f"/{term}/" in path:
            return True
        return path.rsplit("/", 1)[-1].startswith(term)

    async def async_get_index(self, *, force_refresh: bool = False) -> list[dict[str, str]]:
        """Return the bundled IRDB index."""
        if self._entries is not None and not force_refresh:
            return self._entries

        self._entries = await self.hass.async_add_executor_job(self._load_index_entries)
        _LOGGER.debug("IRDB search index ready with %s remotes", len(self._entries))
        return self._entries

    @staticmethod
    def _search_rank(entry: dict[str, str], terms: list[str]) -> tuple[int, str, str]:
        """Rank search results with curated entries before loose text matches."""
        path_lower = entry["path"].lower()
        brand_lower = entry["brand"].lower()
        model_lower = entry["model"].lower()
        label_lower = entry["label"].lower()
        score = 0

        for term in terms:
            if brand_lower == term:
                score += 200
            elif f"/{term}/" in path_lower:
                score += 150
            elif brand_lower.startswith(term):
                score += 120
            elif term in brand_lower:
                score += 80
            elif term in model_lower:
                score += 60
            elif term in label_lower:
                score += 40
            elif term in path_lower:
                score += 20

        return (-score, label_lower, path_lower)

    async def async_search(
        self, query: str, *, device_type: str | None = None
    ) -> list[dict[str, str]]:
        """Search remotes by free text and optional device category."""
        query = query.strip().lower()
        if len(query) < 2:
            return []

        terms = query.split()
        index = await self.async_get_index()
        primary = [
            entry
            for entry in index
            if all(self._term_matches_entry(entry, term) for term in terms)
        ]
        if primary:
            results = primary
        else:
            results = [
                entry
                for entry in index
                if all(term in entry["search_text"] for term in terms)
            ]

        if device_type:
            category = device_type.strip().lower()
            results = [
                entry
                for entry in results
                if entry["device_type"].lower() == category
            ]

        results.sort(key=lambda entry: self._search_rank(entry, terms))
        return results

    async def async_download_remote(self, path: str) -> str:
        """Download a remote .ir file from GitHub."""
        session = async_get_clientsession(self.hass)
        url = IRDB_RAW_URL.format(path=path)
        try:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status != 200:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="irdb_download_failed",
                        translation_placeholders={
                            "path": path,
                            "status": str(response.status),
                        },
                    )
                return await response.text()
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="irdb_download_failed",
                translation_placeholders={"path": path, "status": "timeout"},
            ) from err
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="irdb_download_failed",
                translation_placeholders={"path": path, "status": "network"},
            ) from err

    async def async_preview_remote(self, path: str) -> dict[str, Any]:
        """Return import preview data for a remote."""
        from .flipper_ir import parse_flipper_ir, signals_to_command_map

        content = await self.async_download_remote(path)
        signals = parse_flipper_ir(content)
        commands, skipped = signals_to_command_map(signals)
        return {
            "path": path,
            "signal_count": len(commands),
            "skipped_count": skipped,
            "commands": commands,
        }
