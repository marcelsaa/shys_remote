"""Infrared command helpers."""

from __future__ import annotations

from typing import override

from infrared_protocols.commands import Command as InfraredCommand


class RawInfraredCommand(InfraredCommand):
    """Send previously learned raw IR timings."""

    def __init__(self, timings: list[int], *, modulation: int) -> None:
        """Initialize a raw IR command."""
        super().__init__(modulation=modulation)
        self._timings = timings

    @override
    def get_raw_timings(self) -> list[int]:
        """Return learned raw timings."""
        return self._timings
