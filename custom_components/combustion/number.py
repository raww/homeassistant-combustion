"""Number platform: writable target temperature (and alarm thresholds later)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .combustion_ble.uart import PredictionMode
from .const import DOMAIN
from .entity import CombustionConnectionGatedEntity


class CombustionTargetTemperature(CombustionConnectionGatedEntity, NumberEntity):
    """Writable cook target temperature (Set Prediction)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0.0
    _attr_native_max_value = 102.0
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX

    def __init__(self, connection_manager, control_manager, device_data, default_mode: PredictionMode) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._control = control_manager
        self._default_mode = default_mode
        self._attr_unique_id = f"{device_data.serial_number}--target-temperature"

    @property
    def name(self):
        """Entity name."""
        return "Target temperature"

    async def async_set_native_value(self, value: float) -> None:
        """Send a new target temperature to the probe."""
        await self._control.async_set_target(self._serial, value, self._default_mode)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up number entities (only when active connection is enabled)."""
    probe_manager = hass.data[DOMAIN]
    if not getattr(probe_manager, "active_enabled", False):
        return
    # Task 13 wires the per-probe create callback here.
