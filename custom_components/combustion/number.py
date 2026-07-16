"""Number platform: writable target temperature (and alarm thresholds later)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .combustion_ble.uart import PredictionMode
from .const import DOMAIN
from .entity import CombustionEntity


class CombustionTargetTemperature(CombustionEntity, NumberEntity):
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
        super().__init__(device_data.serial_number)
        self._conn = connection_manager
        self._control = control_manager
        self._serial = device_data.serial_number
        self._default_mode = default_mode
        self.device_serial_number = device_data.serial_number
        self._attr_unique_id = f"{device_data.serial_number}--target-temperature"

    @property
    def name(self):
        """Entity name."""
        return "Target temperature"

    @property
    def available(self) -> bool:
        """Only available while actively connected."""
        return self._conn.is_connected(self._serial)

    async def async_added_to_hass(self) -> None:
        """Update state when the probe's connection state changes.

        This entity has no `probe_manager`, so it does NOT call the base
        `CombustionEntity.async_added_to_hass`, which would try to register a
        listener against a nonexistent `probe_manager` attribute. Instead it
        listens directly on the `ConnectionManager` for connect/disconnect.
        """
        self.async_on_remove(self._conn.add_connection_listener(self._handle_conn_update))

    @callback
    def _handle_conn_update(self) -> None:
        """Refresh HA state on a connection change."""
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Send a new target temperature to the probe."""
        await self._control.async_set_target(self._serial, value, self._default_mode)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up number entities (only when active connection is enabled)."""
    probe_manager = hass.data[DOMAIN]
    if not getattr(probe_manager, "active_enabled", False):
        return
    # Task 13 wires the per-probe create callback here.
