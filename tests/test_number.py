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


class _Control:
    """Fake control manager recording set-target calls."""

    def __init__(self):
        """Initialize with an empty call log."""
        self.calls = []

    async def async_set_target(self, serial, temp_c, mode):
        """Record the call args."""
        self.calls.append((serial, temp_c, mode))

    async def async_set_high_alarm(self, serial, temp_c):
        """Record the high-alarm call args."""
        self.calls.append((serial, temp_c))

    async def async_set_low_alarm(self, serial, temp_c):
        """Record the low-alarm call args."""
        self.calls.append((serial, temp_c))


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
