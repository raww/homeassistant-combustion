"""Tests for the control select entities."""
import pytest
from combustion.combustion_ble.uart import PowerMode, PredictionMode
from combustion.select import (
    CombustionColourSelect,
    CombustionModeSelect,
    CombustionPowerModeSelect,
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


class _LastState:
    """Fake restored state object mimicking homeassistant.core.State."""

    def __init__(self, state):
        """Initialize with the given state string."""
        self.state = state


class _Control:
    """Fake control manager recording calls to each setter."""

    def __init__(self):
        """Initialize with empty call logs."""
        self.mode_calls = []
        self.colour_calls = []
        self.power_mode_calls = []

    async def async_set_mode(self, serial, mode):
        """Record a prediction-mode call."""
        self.mode_calls.append((serial, mode))

    async def async_set_probe_colour(self, serial, colour):
        """Record a probe-colour call."""
        self.colour_calls.append((serial, colour))

    async def async_set_power_mode(self, serial, mode):
        """Record a power-mode call."""
        self.power_mode_calls.append((serial, mode))


class _DeviceData:
    """Minimal stand-in for CombustionProbeData."""

    serial_number = "S1"
    device_type = "PROBE"


@pytest.mark.asyncio
async def test_select_mode_option_maps_to_enum():
    """Selecting a mode label sends the mapped PredictionMode."""
    control = _Control()
    ent = CombustionModeSelect(_Conn(), control, _DeviceData())
    await ent.async_select_option("Removal and resting")
    assert control.mode_calls == [("S1", PredictionMode.REMOVAL_AND_RESTING)]


@pytest.mark.asyncio
async def test_select_colour_option_maps_to_index():
    """Selecting a colour label sends the mapped zero-based index."""
    control = _Control()
    ent = CombustionColourSelect(_Conn(), control, _DeviceData())
    await ent.async_select_option("Color 3")
    assert control.colour_calls == [("S1", 2)]


@pytest.mark.asyncio
async def test_select_power_mode_option_maps_to_enum():
    """Selecting a power-mode label sends the mapped PowerMode."""
    control = _Control()
    ent = CombustionPowerModeSelect(_Conn(), control, _DeviceData())
    await ent.async_select_option("Always on")
    assert control.power_mode_calls == [("S1", PowerMode.ALWAYS_ON)]


@pytest.mark.asyncio
async def test_available_reflects_connection():
    """Each select is only available while the probe connection is live."""
    control = _Control()
    ent = CombustionModeSelect(_Conn(connected=True), control, _DeviceData())
    assert ent.available is True

    ent2 = CombustionModeSelect(_Conn(connected=False), control, _DeviceData())
    assert ent2.available is False


@pytest.mark.asyncio
async def test_mode_select_restores_option():
    """On restart, the mode select restores its last displayed option (no ControlManager seed)."""
    control = _Control()
    ent = CombustionModeSelect(_Conn(), control, _DeviceData())

    async def _fake_last_state():
        return _LastState("Removal and resting")

    ent.async_get_last_state = _fake_last_state

    await ent.async_added_to_hass()

    assert ent.current_option == "Removal and resting"
    assert control.mode_calls == []
