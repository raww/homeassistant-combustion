"""Tests for the control select entities."""
import pytest
from combustion.combustion_ble.uart import PowerMode
from combustion.select import CombustionPowerModeSelect


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
    """Fake control manager recording calls to each setter."""

    def __init__(self):
        """Initialize with empty call logs."""
        self.power_mode_calls = []

    async def async_set_power_mode(self, serial, mode):
        """Record a power-mode call."""
        self.power_mode_calls.append((serial, mode))


class _DeviceData:
    """Minimal stand-in for CombustionProbeData."""

    serial_number = "S1"
    device_type = "PROBE"


@pytest.mark.asyncio
async def test_select_power_mode_option_maps_to_enum():
    """Selecting a power-mode label sends the mapped PowerMode."""
    control = _Control()
    ent = CombustionPowerModeSelect(_Conn(), control, _DeviceData())
    await ent.async_select_option("Always on")
    assert control.power_mode_calls == [("S1", PowerMode.ALWAYS_ON)]


@pytest.mark.asyncio
async def test_available_reflects_connection():
    """The select is only available while the probe connection is live."""
    control = _Control()
    ent = CombustionPowerModeSelect(_Conn(connected=True), control, _DeviceData())
    assert ent.available is True

    ent2 = CombustionPowerModeSelect(_Conn(connected=False), control, _DeviceData())
    assert ent2.available is False
