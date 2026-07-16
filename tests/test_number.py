"""Tests for the target-temperature number entity."""
import pytest
from combustion.combustion_ble.uart import PredictionMode
from combustion.number import CombustionTargetTemperature


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
