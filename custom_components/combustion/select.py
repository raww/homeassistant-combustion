"""Select platform: prediction mode, probe colour, and power mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .combustion_ble.uart import PowerMode, PredictionMode
from .const import DOMAIN
from .entity import CombustionConnectionGatedEntity

_MODE_OPTIONS = {
    "Off": PredictionMode.NONE,
    "Time to removal": PredictionMode.TIME_TO_REMOVAL,
    "Removal and resting": PredictionMode.REMOVAL_AND_RESTING,
}

_COLOUR_OPTIONS = {f"Color {n}": n - 1 for n in range(1, 9)}

_POWER_MODE_OPTIONS = {
    "Normal": PowerMode.NORMAL,
    "Always on": PowerMode.ALWAYS_ON,
}


class CombustionModeSelect(CombustionConnectionGatedEntity, SelectEntity):
    """Writable prediction mode (Off / Time to removal / Removal and resting)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(_MODE_OPTIONS.keys())

    def __init__(self, connection_manager, control_manager, device_data) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._control = control_manager
        self._attr_unique_id = f"{device_data.serial_number}--prediction-mode"

    @property
    def name(self):
        """Entity name."""
        return "Prediction mode"

    async def async_select_option(self, option: str) -> None:
        """Send the mapped prediction mode to the probe."""
        await self._control.async_set_mode(self._serial, _MODE_OPTIONS[option])


class CombustionColourSelect(CombustionConnectionGatedEntity, SelectEntity):
    """Writable probe colour (Color 1..8)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(_COLOUR_OPTIONS.keys())

    def __init__(self, connection_manager, control_manager, device_data) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._control = control_manager
        self._attr_unique_id = f"{device_data.serial_number}--probe-colour"

    @property
    def name(self):
        """Entity name."""
        return "Probe colour"

    async def async_select_option(self, option: str) -> None:
        """Send the mapped colour index to the probe."""
        await self._control.async_set_probe_colour(self._serial, _COLOUR_OPTIONS[option])


class CombustionPowerModeSelect(CombustionConnectionGatedEntity, SelectEntity):
    """Writable power mode (Normal / Always on)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(_POWER_MODE_OPTIONS.keys())

    def __init__(self, connection_manager, control_manager, device_data) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._control = control_manager
        self._attr_unique_id = f"{device_data.serial_number}--power-mode"

    @property
    def name(self):
        """Entity name."""
        return "Power mode"

    async def async_select_option(self, option: str) -> None:
        """Send the mapped power mode to the probe."""
        await self._control.async_set_power_mode(self._serial, _POWER_MODE_OPTIONS[option])


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up select entities (only when active connection is enabled)."""
    probe_manager = hass.data[DOMAIN]
    if not getattr(probe_manager, "active_enabled", False):
        return
    # Task 13 wires the per-probe create callback here.
