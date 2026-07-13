"""Tests for the RF/IR backend dispatch in manager.py and remote.py.

These exercise the actual integration modules (not just signal_transport.py's
pure helpers), relying on the stubs installed in conftest.py for the sibling
``infrared``/``radio_frequency`` components and the ``infrared_protocols``
package.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import shys_remote.manager as manager_module
import shys_remote.remote as remote_module
from shys_remote.command import RawInfraredCommand
from shys_remote.signal_transport import RawSignalCommand

RemoteManager = manager_module.RemoteManager


def _manager() -> RemoteManager:
    """Build a RemoteManager without running __init__ (build_command is self-independent)."""
    return RemoteManager.__new__(RemoteManager)


def _subentry(*, transmitter_entity_id: str, **extra_data) -> SimpleNamespace:
    return SimpleNamespace(data={"transmitter_entity_id": transmitter_entity_id, **extra_data})


def test_build_command_returns_raw_signal_command_for_rf() -> None:
    command_data = {
        "command": [350, -1050, 350, -350],
        "carrier_frequency": 433_920_000,
        "medium": "rf",
        "backend": "homeassistant_radio_frequency",
    }
    subentry = _subentry(transmitter_entity_id="switch.rf_transmitter")

    command = _manager().build_command(command_data, subentry)

    assert isinstance(command, RawSignalCommand)
    assert command.frequency == 433_920_000
    assert command.get_raw_timings() == [350, -1050, 350, -350]
    assert command.transport_entity_id == "switch.rf_transmitter"


def test_build_command_returns_raw_infrared_command_for_ir() -> None:
    command_data = {
        "command": [9000, -4500, 560],
        "carrier_frequency": 38000,
    }
    subentry = _subentry(transmitter_entity_id="remote.ir_blaster")

    command = _manager().build_command(command_data, subentry)

    assert isinstance(command, RawInfraredCommand)
    assert command.get_raw_timings() == [9000, -4500, 560]


def test_send_output_command_dispatches_to_radio_frequency(monkeypatch) -> None:
    sent_calls = []

    async def fake_rf_send(hass, entity_id, command, *, context=None):
        sent_calls.append((entity_id, command.get_raw_timings(), command.frequency))

    async def fake_ir_send(hass, entity_id, command, *, context=None):
        raise AssertionError("infrared.async_send_command should not be called for RF")

    monkeypatch.setattr(
        "homeassistant.components.radio_frequency.async_send_command", fake_rf_send
    )
    monkeypatch.setattr("homeassistant.components.infrared.async_send_command", fake_ir_send)

    command_data = {
        "command": [350, -1050, 350, -350],
        "carrier_frequency": 433_920_000,
        "medium": "rf",
        "backend": "homeassistant_radio_frequency",
    }
    subentry = _subentry(transmitter_entity_id="switch.rf_transmitter")

    asyncio.run(
        remote_module.async_send_output_command(
            hass=object(),
            manager=_manager(),
            subentry=subentry,
            command_data=command_data,
        )
    )

    assert sent_calls == [("switch.rf_transmitter", [350, -1050, 350, -350], 433_920_000)]


def test_send_output_command_dispatches_to_infrared(monkeypatch) -> None:
    sent_calls = []

    async def fake_ir_send(hass, entity_id, command, *, context=None):
        sent_calls.append((entity_id, command.get_raw_timings()))

    async def fake_rf_send(hass, entity_id, command, *, context=None):
        raise AssertionError("radio_frequency.async_send_command should not be called for IR")

    monkeypatch.setattr(
        "homeassistant.components.infrared.async_get_emitters",
        lambda hass: ["remote.ir_blaster"],
    )
    monkeypatch.setattr("homeassistant.components.infrared.async_send_command", fake_ir_send)
    monkeypatch.setattr(
        "homeassistant.components.radio_frequency.async_send_command", fake_rf_send
    )

    command_data = {
        "command": [9000, -4500, 560],
        "carrier_frequency": 38000,
    }
    subentry = _subentry(transmitter_entity_id="remote.ir_blaster")

    asyncio.run(
        remote_module.async_send_output_command(
            hass=object(),
            manager=_manager(),
            subentry=subentry,
            command_data=command_data,
        )
    )

    assert sent_calls == [("remote.ir_blaster", [9000, -4500, 560])]


class _FakeSignal:
    def __init__(self, timings: list[int], modulation: int = 38000) -> None:
        self.timings = timings
        self.modulation = modulation


def _queued_subscribe_receiver(signals: list[_FakeSignal]):
    """Return an async_subscribe_receiver stub that yields one signal per call."""

    def fake_subscribe_receiver(hass, entity_id, callback_):
        callback_(signals.pop(0))

        def _unsubscribe() -> None:
            return None

        return _unsubscribe

    return fake_subscribe_receiver


def _rf_subentry(**extra_data) -> SimpleNamespace:
    return SimpleNamespace(
        data={
            "transmitter_entity_id": "switch.rf_transmitter",
            "receiver_entity_id": "remote.ir_receiver",
            "medium": "rf",
            "rf_frequency": 433_920_000,
            **extra_data,
        },
        subentry_id="dev1",
        title="Test RF device",
    )


def _manager_with_entry() -> RemoteManager:
    manager = _manager()
    manager.commands = {}
    manager.entry = SimpleNamespace(options={})
    return manager


def test_learn_command_stores_device_rf_frequency_not_signal_modulation(monkeypatch) -> None:
    """ESPHome's infrared-compatible receiver never reports the RF frequency in
    signal.modulation - it only ever sends raw timings. Using signal.modulation
    for RF would silently store the IR default (~38 kHz) instead of the
    device's real RF transmit frequency."""
    timings = [350, -1050, 350, -350]

    monkeypatch.setattr(
        "homeassistant.components.infrared.async_get_receivers",
        lambda hass: ["remote.ir_receiver"],
    )
    monkeypatch.setattr(
        "homeassistant.components.infrared.async_subscribe_receiver",
        _queued_subscribe_receiver(
            [_FakeSignal(timings), _FakeSignal(list(timings))]
        ),
    )

    manager = _manager_with_entry()
    captured: dict = {}

    async def fake_add_command(subentry, name, command_data):
        captured["command_data"] = command_data

    manager.async_add_command = fake_add_command

    asyncio.run(
        remote_module.async_learn_command(
            hass=object(),
            manager=manager,
            subentry=_rf_subentry(),
            command_name="power",
        )
    )

    assert captured["command_data"]["carrier_frequency"] == 433_920_000
    assert captured["command_data"]["command"] == timings


def test_learn_command_rf_requires_two_matching_captures(monkeypatch) -> None:
    """A single noisy RF capture must not be enough to store a signal - the
    KC868-style receivers this integration targets are known to cut each raw
    dump at a slightly different point, so two captures must agree first."""
    monkeypatch.setattr(
        "homeassistant.components.infrared.async_get_receivers",
        lambda hass: ["remote.ir_receiver"],
    )
    monkeypatch.setattr(
        "homeassistant.components.infrared.async_subscribe_receiver",
        _queued_subscribe_receiver(
            [
                _FakeSignal([350, -1050, 350, -350]),
                _FakeSignal([9000, -4500, 560, -560]),  # unrelated capture
            ]
        ),
    )

    manager = _manager_with_entry()

    async def fake_add_command(subentry, name, command_data):
        raise AssertionError("inconsistent RF captures must not be stored")

    manager.async_add_command = fake_add_command

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            remote_module.async_learn_command(
                hass=object(),
                manager=manager,
                subentry=_rf_subentry(),
                command_name="power",
            )
        )

    assert exc_info.value.translation_key == "rf_learn_inconsistent"


def test_learn_command_rf_second_empty_capture_raises_empty_signal(monkeypatch) -> None:
    monkeypatch.setattr(
        "homeassistant.components.infrared.async_get_receivers",
        lambda hass: ["remote.ir_receiver"],
    )
    monkeypatch.setattr(
        "homeassistant.components.infrared.async_subscribe_receiver",
        _queued_subscribe_receiver(
            [_FakeSignal([350, -1050, 350, -350]), _FakeSignal([])]
        ),
    )

    manager = _manager_with_entry()

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            remote_module.async_learn_command(
                hass=object(),
                manager=manager,
                subentry=_rf_subentry(),
                command_name="power",
            )
        )

    assert exc_info.value.translation_key == "empty_signal"


def test_learn_command_ir_only_needs_one_capture(monkeypatch) -> None:
    """IR learning behavior must stay unchanged: exactly one capture, no
    second subscribe call - unlike the new RF confirmation requirement."""
    monkeypatch.setattr(
        "homeassistant.components.infrared.async_get_receivers",
        lambda hass: ["remote.ir_receiver"],
    )
    monkeypatch.setattr(
        "homeassistant.components.infrared.async_get_emitters",
        lambda hass: ["remote.ir_blaster"],
    )
    monkeypatch.setattr(
        "homeassistant.components.infrared.async_subscribe_receiver",
        _queued_subscribe_receiver([_FakeSignal([9000, -4500, 560, -560])]),
    )

    manager = _manager_with_entry()
    captured: dict = {}

    async def fake_add_command(subentry, name, command_data):
        captured["command_data"] = command_data

    manager.async_add_command = fake_add_command

    subentry = SimpleNamespace(
        data={
            "transmitter_entity_id": "remote.ir_blaster",
            "receiver_entity_id": "remote.ir_receiver",
        },
        subentry_id="dev2",
        title="Test IR device",
    )

    asyncio.run(
        remote_module.async_learn_command(
            hass=object(),
            manager=manager,
            subentry=subentry,
            command_name="power",
        )
    )

    assert captured["command_data"]["command"] == [9000, -4500, 560, -560]


def test_send_output_command_rf_without_transmitter_raises() -> None:
    command_data = {
        "command": [350, -1050],
        "carrier_frequency": 433_920_000,
        "medium": "rf",
        "backend": "homeassistant_radio_frequency",
    }
    subentry = SimpleNamespace(data={})

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            remote_module.async_send_output_command(
                hass=object(),
                manager=_manager(),
                subentry=subentry,
                command_data=command_data,
            )
        )

    assert exc_info.value.translation_key == "invalid_emitter"
