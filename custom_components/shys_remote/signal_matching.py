"""Helpers to compare learned and received timing sequences."""

from __future__ import annotations

_MIN_TOLERANCE_US = 100


def timings_match(
    expected: list[int],
    actual: list[int],
    tolerance_percent: float,
) -> bool:
    """Return whether two timing sequences match within tolerance."""
    if len(actual) < len(expected):
        return False

    for expected_value, actual_value in zip(
        expected, actual[: len(expected)], strict=True
    ):
        difference = abs(expected_value - actual_value)
        allowed = max(abs(expected_value), abs(actual_value)) * tolerance_percent / 100
        if difference > max(allowed, _MIN_TOLERANCE_US):
            return False

    return True


def signal_matches(
    learned: list[int],
    received: list[int],
    tolerance_percent: float,
) -> bool:
    """Return whether a received signal matches a learned pattern."""
    if not learned or not received or len(received) < len(learned):
        return False

    return timings_match(learned, received, tolerance_percent)


def captures_match(
    first: list[int],
    second: list[int],
    tolerance_percent: float,
) -> bool:
    """Return whether two raw learn captures represent the same signal.

    Unlike signal_matches(), neither side is assumed to be the canonical
    "learned" pattern - this compares two fresh captures symmetrically, so
    the shorter one is used as the reference (a longer capture just means
    extra trailing idle/noise, which is expected and not a mismatch).
    """
    if not first or not second:
        return False

    shorter, longer = (first, second) if len(first) <= len(second) else (second, first)
    return timings_match(shorter, longer, tolerance_percent)
