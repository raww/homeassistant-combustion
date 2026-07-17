"""Tests for the control button entities."""
import pytest
from combustion.button import (
    CombustionResetFoodSafeButton,
    CombustionResetProbeButton,
    CombustionSilenceButton,
)


class _Conn:
    """Fake connection manager with a configurable connected state."""

    def __init__(self, connected: bool = True) -> None:
        """Initialize with the given connected state."""
        self._connected = connected

    def is_connected(self, serial):
        """Return the configured connected state."""
        return self._connected

    def add_connection_listener(self, listener):
        """Return a no-op unsubscribe callback."""
        return lambda: None


class _Control:
    """Fake control manager recording calls to each action."""

    def __init__(self):
        """Initialize with empty call logs."""
        self.silenced = []
        self.reset_probe = []
        self.reset_food_safe = []

    async def async_silence(self, serial):
        """Record a silence call."""
        self.silenced.append(serial)

    async def async_reset_probe(self, serial):
        """Record a reset-probe call."""
        self.reset_probe.append(serial)

    async def async_reset_food_safe(self, serial):
        """Record a reset-food-safe call."""
        self.reset_food_safe.append(serial)


class _DeviceData:
    """Minimal stand-in for CombustionProbeData."""

    serial_number = "S1"
    device_type = "PROBE"


@pytest.mark.asyncio
async def test_silence_button_calls_control():
    """Pressing silence calls ControlManager.async_silence."""
    control = _Control()
    ent = CombustionSilenceButton(_Conn(), control, _DeviceData())
    await ent.async_press()
    assert control.silenced == ["S1"]


@pytest.mark.asyncio
async def test_reset_probe_button_calls_control():
    """Pressing reset thermometer calls ControlManager.async_reset_probe."""
    control = _Control()
    ent = CombustionResetProbeButton(_Conn(), control, _DeviceData())
    await ent.async_press()
    assert control.reset_probe == ["S1"]


@pytest.mark.asyncio
async def test_reset_food_safe_button_calls_control():
    """Pressing reset food safe calls ControlManager.async_reset_food_safe."""
    control = _Control()
    ent = CombustionResetFoodSafeButton(_Conn(), control, _DeviceData())
    await ent.async_press()
    assert control.reset_food_safe == ["S1"]


def test_reset_buttons_disabled_by_default():
    """Both reset buttons are disabled by default (footgun guard)."""
    probe_ent = CombustionResetProbeButton(_Conn(), _Control(), _DeviceData())
    food_safe_ent = CombustionResetFoodSafeButton(_Conn(), _Control(), _DeviceData())
    assert probe_ent.entity_registry_enabled_default is False
    assert food_safe_ent.entity_registry_enabled_default is False


def test_silence_button_enabled_by_default():
    """The silence button is not disabled by default."""
    ent = CombustionSilenceButton(_Conn(), _Control(), _DeviceData())
    assert ent.entity_registry_enabled_default is True
