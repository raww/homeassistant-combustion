"""Tests for the target-temperature and alarm number entities."""
import pytest
from combustion.combustion_ble.uart import PredictionMode
from combustion.number import (
    CombustionHighAlarm,
    CombustionLowAlarm,
    CombustionTargetTemperature,
)


class _Conn:
    """Fake connection manager with a configurable connected state."""

    def __init__(self, connected: bool = True) -> None:
        """Initialize with the given connected state."""
        self._connected = connected

    def is_connected(self, serial):
        """Return the configured connected state."""
        return self._connected

    def add_connection_listener(self, callback):
        """Return a no-op remover, matching the real ConnectionManager's API."""
        return lambda: None


class _Control:
    """Fake control manager recording set-target calls."""

    def __init__(self):
        """Initialize with an empty call log."""
        self.calls = []
        self.remember_calls = []

    async def async_set_target(self, serial, temp_c, mode):
        """Record the call args."""
        self.calls.append((serial, temp_c, mode))

    async def async_set_high_alarm(self, serial, temp_c):
        """Record the high-alarm call args."""
        self.calls.append((serial, temp_c))

    async def async_set_low_alarm(self, serial, temp_c):
        """Record the low-alarm call args."""
        self.calls.append((serial, temp_c))

    def remember_target(self, serial, temp_c, mode):
        """Record a remember-target seed call."""
        self.remember_calls.append(("target", serial, temp_c, mode))

    def remember_high_alarm(self, serial, temp_c):
        """Record a remember-high-alarm seed call."""
        self.remember_calls.append(("high", serial, temp_c))

    def remember_low_alarm(self, serial, temp_c):
        """Record a remember-low-alarm seed call."""
        self.remember_calls.append(("low", serial, temp_c))


class _LastState:
    """Fake restored state object mimicking homeassistant.core.State."""

    def __init__(self, state):
        """Initialize with the given state string."""
        self.state = state


class _DeviceData:
    """Minimal stand-in for CombustionProbeData."""

    serial_number = "S1"
    device_type = "PROBE"


@pytest.mark.asyncio
async def test_set_native_value_calls_control():
    """Setting the number sends a target to the ControlManager."""
    control = _Control()
    ent = CombustionTargetTemperature(_Conn(), control, _DeviceData(), default_mode=PredictionMode.TIME_TO_REMOVAL)
    await ent.async_set_native_value(63.0)
    assert control.calls == [("S1", 63.0, PredictionMode.TIME_TO_REMOVAL)]


@pytest.mark.asyncio
async def test_available_reflects_connection():
    """The entity is only available while the probe connection is live."""
    control = _Control()
    ent = CombustionTargetTemperature(
        _Conn(connected=True), control, _DeviceData(), default_mode=PredictionMode.TIME_TO_REMOVAL
    )
    assert ent.available is True

    ent2 = CombustionTargetTemperature(
        _Conn(connected=False), control, _DeviceData(), default_mode=PredictionMode.TIME_TO_REMOVAL
    )
    assert ent2.available is False


@pytest.mark.asyncio
async def test_high_alarm_sets_value_via_control():
    """Setting the high-alarm number calls ControlManager.async_set_high_alarm."""
    control = _Control()
    ent = CombustionHighAlarm(_Conn(), control, _DeviceData())
    await ent.async_set_native_value(95.0)
    assert control.calls == [("S1", 95.0)]


@pytest.mark.asyncio
async def test_low_alarm_sets_value_via_control():
    """Setting the low-alarm number calls ControlManager.async_set_low_alarm."""
    control = _Control()
    ent = CombustionLowAlarm(_Conn(), control, _DeviceData())
    await ent.async_set_native_value(40.0)
    assert control.calls == [("S1", 40.0)]


@pytest.mark.asyncio
async def test_set_native_value_updates_displayed_value():
    """Setting the target number updates native_value so the entity isn't write-only."""
    control = _Control()
    ent = CombustionTargetTemperature(_Conn(), control, _DeviceData(), default_mode=PredictionMode.TIME_TO_REMOVAL)
    await ent.async_set_native_value(63.0)
    assert ent.native_value == 63.0


@pytest.mark.asyncio
async def test_target_restores_and_seeds():
    """On restart, the target entity restores its last value and seeds ControlManager (no send)."""
    control = _Control()
    ent = CombustionTargetTemperature(_Conn(), control, _DeviceData(), default_mode=PredictionMode.TIME_TO_REMOVAL)

    async def _fake_last_state():
        return _LastState("63.0")

    ent.async_get_last_state = _fake_last_state

    await ent.async_added_to_hass()

    assert ent.native_value == 63.0
    assert control.calls == []
    assert control.remember_calls == [("target", "S1", 63.0, PredictionMode.TIME_TO_REMOVAL)]


@pytest.mark.asyncio
async def test_high_alarm_restores_and_seeds():
    """On restart, the high-alarm entity restores its last value and seeds ControlManager (no send)."""
    control = _Control()
    ent = CombustionHighAlarm(_Conn(), control, _DeviceData())

    async def _fake_last_state():
        return _LastState("95.0")

    ent.async_get_last_state = _fake_last_state

    await ent.async_added_to_hass()

    assert ent.native_value == 95.0
    assert control.calls == []
    assert control.remember_calls == [("high", "S1", 95.0)]


@pytest.mark.asyncio
async def test_target_restore_with_no_prior_state_does_not_seed():
    """With no restorable state (fresh install), nothing is seeded and nothing is sent."""
    control = _Control()
    ent = CombustionTargetTemperature(_Conn(), control, _DeviceData(), default_mode=PredictionMode.TIME_TO_REMOVAL)

    async def _fake_last_state():
        return None

    ent.async_get_last_state = _fake_last_state

    await ent.async_added_to_hass()

    assert control.calls == []
    assert control.remember_calls == []
