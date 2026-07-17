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
async def test_select_power_mode_option_maps_to_enum():
    """Selecting a power-mode label sends the mapped PowerMode and reflects it."""
    control = _Control()
    ent = CombustionPowerModeSelect(_Conn(), control, _DeviceData())
    await ent.async_select_option("Always on")
    assert control.power_mode_calls == [("S1", PowerMode.ALWAYS_ON)]
    # Optimistic: the entity now shows the selected option, not "unknown".
    assert ent.current_option == "Always on"


def test_power_mode_defaults_to_normal():
    """With no readback source, the entity shows the factory default, never unknown."""
    ent = CombustionPowerModeSelect(_Conn(), _Control(), _DeviceData())
    assert ent.current_option == "Normal"


@pytest.mark.asyncio
async def test_power_mode_restores_last_option():
    """On restart, the entity restores the last displayed option."""
    ent = CombustionPowerModeSelect(_Conn(), _Control(), _DeviceData())

    async def _fake_last_state():
        return _LastState("Always on")

    ent.async_get_last_state = _fake_last_state
    await ent.async_added_to_hass()
    assert ent.current_option == "Always on"


@pytest.mark.asyncio
async def test_available_reflects_connection():
    """The select is only available while the probe connection is live."""
    control = _Control()
    ent = CombustionPowerModeSelect(_Conn(connected=True), control, _DeviceData())
    assert ent.available is True

    ent2 = CombustionPowerModeSelect(_Conn(connected=False), control, _DeviceData())
    assert ent2.available is False
