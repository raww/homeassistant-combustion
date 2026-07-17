"""Number platform: writable target temperature (and alarm thresholds later)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .combustion_ble.uart import PredictionMode
from .const import DOMAIN
from .entity import CombustionConnectionGatedEntity


async def _async_restore_native_value(entity) -> None:
    """Register the connection listener and restore/seed the last known value.

    Shared by the three stateful number entities below. Each overrides
    `async_added_to_hass` (rather than calling the base), so this also takes
    over the base's connection-listener registration. Seeding must NOT send a
    command — the device already holds its own state after a restart.
    """
    entity.async_on_remove(entity._conn.add_connection_listener(entity._handle_conn_update))
    last = await entity.async_get_last_state()
    if last is not None and last.state not in (None, "unknown", "unavailable"):
        try:
            value = float(last.state)
        except (TypeError, ValueError):
            value = None
        if value is not None:
            entity._attr_native_value = value
            entity._seed_control(value)


class CombustionTargetTemperature(CombustionConnectionGatedEntity, RestoreEntity, NumberEntity):
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
        self._attr_native_value = value
        await self._control.async_set_target(self._serial, value, self._default_mode)
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last target temperature and seed ControlManager (no send)."""
        await _async_restore_native_value(self)

    def _seed_control(self, value: float) -> None:
        """Seed the remembered target/mode without sending a command."""
        self._control.remember_target(self._serial, value, self._default_mode)


class CombustionHighAlarm(CombustionConnectionGatedEntity, RestoreEntity, NumberEntity):
    """Writable high-alarm threshold for the probe's core sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0.0
    _attr_native_max_value = 300.0
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, connection_manager, control_manager, device_data) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._control = control_manager
        self._attr_unique_id = f"{device_data.serial_number}--high-alarm-setpoint"

    @property
    def name(self):
        """Entity name."""
        return "High alarm"

    async def async_set_native_value(self, value: float) -> None:
        """Send a new high-alarm threshold to the probe."""
        self._attr_native_value = value
        await self._control.async_set_high_alarm(self._serial, value)
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last high-alarm threshold and seed ControlManager (no send)."""
        await _async_restore_native_value(self)

    def _seed_control(self, value: float) -> None:
        """Seed the remembered high-alarm threshold without sending a command."""
        self._control.remember_high_alarm(self._serial, value)


class CombustionLowAlarm(CombustionConnectionGatedEntity, RestoreEntity, NumberEntity):
    """Writable low-alarm threshold for the probe's core sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0.0
    _attr_native_max_value = 300.0
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, connection_manager, control_manager, device_data) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._control = control_manager
        self._attr_unique_id = f"{device_data.serial_number}--low-alarm-setpoint"

    @property
    def name(self):
        """Entity name."""
        return "Low alarm"

    async def async_set_native_value(self, value: float) -> None:
        """Send a new low-alarm threshold to the probe."""
        self._attr_native_value = value
        await self._control.async_set_low_alarm(self._serial, value)
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last low-alarm threshold and seed ControlManager (no send)."""
        await _async_restore_native_value(self)

    def _seed_control(self, value: float) -> None:
        """Seed the remembered low-alarm threshold without sending a command."""
        self._control.remember_low_alarm(self._serial, value)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up number entities (only when active connection is enabled)."""
    probe_manager = hass.data[DOMAIN]
    if not getattr(probe_manager, "active_enabled", False):
        return
    conn = probe_manager.connection_manager
    control = probe_manager.control_manager

    def _create(probe_data):
        async_add_entities([
            CombustionTargetTemperature(
                conn, control, probe_data, default_mode=PredictionMode.TIME_TO_REMOVAL
            ),
            CombustionHighAlarm(conn, control, probe_data),
            CombustionLowAlarm(conn, control, probe_data),
        ])

    conn.add_new_probe_listener(_create)
