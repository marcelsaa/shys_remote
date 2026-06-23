"""Map common remote signal names to Material Design Icons."""

from __future__ import annotations

import re

DEFAULT_SIGNAL_ICON = "mdi:remote"

_EXACT_ICONS: dict[str, str] = {
    "back": "mdi:arrow-left",
    "blue": "mdi:alpha-b-circle",
    "cc": "mdi:closed-caption",
    "ch_dn": "mdi:chevron-down",
    "ch_down": "mdi:chevron-down",
    "ch_up": "mdi:chevron-up",
    "channel_down": "mdi:chevron-down",
    "channel_up": "mdi:chevron-up",
    "down": "mdi:chevron-down",
    "enter": "mdi:keyboard-return",
    "exit": "mdi:exit-to-app",
    "fast_forward": "mdi:fast-forward",
    "ff": "mdi:fast-forward",
    "fwd": "mdi:fast-forward",
    "green": "mdi:alpha-g-circle",
    "guide": "mdi:television-guide",
    "home": "mdi:home",
    "info": "mdi:information-outline",
    "input": "mdi:import",
    "left": "mdi:chevron-left",
    "menu": "mdi:menu",
    "mute": "mdi:volume-mute",
    "next": "mdi:skip-next",
    "ok": "mdi:checkbox-marked-circle-outline",
    "pause": "mdi:pause",
    "play": "mdi:play",
    "power": "mdi:power",
    "power_off": "mdi:power",
    "power_on": "mdi:power",
    "prev": "mdi:skip-previous",
    "previous": "mdi:skip-previous",
    "red": "mdi:alpha-r-circle",
    "rew": "mdi:rewind",
    "rewind": "mdi:rewind",
    "right": "mdi:chevron-right",
    "select": "mdi:checkbox-marked-circle-outline",
    "source": "mdi:input-hdmi",
    "stop": "mdi:stop",
    "subtitle": "mdi:subtitles",
    "up": "mdi:chevron-up",
    "vol_dn": "mdi:volume-minus",
    "vol_down": "mdi:volume-minus",
    "vol_up": "mdi:volume-plus",
    "volume_down": "mdi:volume-minus",
    "volume_up": "mdi:volume-plus",
    "yellow": "mdi:alpha-y-circle",
}

_NUMERIC_ICON = re.compile(r"^(?:num(?:ber)?|digit)?[_-]?([0-9])$")


def _normalize_signal_name(signal_name: str) -> str:
    """Normalize a stored signal name for icon lookup."""
    return signal_name.strip().lower().replace("-", "_")


def _numeric_icon(normalized: str) -> str | None:
    """Return an icon for digit keys such as 0-9 or num_3."""
    if len(normalized) == 1 and normalized.isdigit():
        return f"mdi:numeric-{normalized}-box"

    match = _NUMERIC_ICON.fullmatch(normalized)
    if match:
        return f"mdi:numeric-{match.group(1)}-box"

    return None


def icon_for_signal(signal_name: str) -> str:
    """Return a plausible MDI icon for a standard remote button name."""
    normalized = _normalize_signal_name(signal_name)

    if not normalized:
        return DEFAULT_SIGNAL_ICON

    exact_icon = _EXACT_ICONS.get(normalized)
    if exact_icon is not None:
        return exact_icon

    numeric_icon = _numeric_icon(normalized)
    if numeric_icon is not None:
        return numeric_icon

    if "vol" in normalized:
        if normalized.endswith("_up") or normalized.endswith("up"):
            return "mdi:volume-plus"
        if normalized.endswith(("_dn", "_down")) or normalized.endswith("down"):
            return "mdi:volume-minus"

    if normalized.startswith("ch_") or normalized.startswith("channel_"):
        if normalized.endswith("_up") or normalized.endswith("up"):
            return "mdi:chevron-up"
        if normalized.endswith(("_dn", "_down")) or normalized.endswith("down"):
            return "mdi:chevron-down"

    if normalized.startswith("power"):
        return "mdi:power"

    return DEFAULT_SIGNAL_ICON
