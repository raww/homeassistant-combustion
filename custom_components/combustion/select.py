"""Select platform: probe power mode.

Prediction-mode and probe-colour selects were removed pending on-hardware
validation (they had no observable effect).
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .combustion_ble.uart import PowerMode
from .const import DOMAIN
from .entity import CombustionConnectionGatedEntity

_POWER_MODE_OPTIONS = {
    "Normal": PowerMode.NORMAL,
    "Always on": PowerMode.ALWAYS_ON,
}


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
    conn = probe_manager.connection_manager
    control = probe_manager.control_manager

    def _create(probe_data):
        async_add_entities([
            CombustionPowerModeSelect(conn, control, probe_data),
        ])

    conn.add_new_probe_listener(_create)
