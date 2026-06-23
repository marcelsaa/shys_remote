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
