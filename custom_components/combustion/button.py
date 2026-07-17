"""Button platform: silence alarms and destructive resets."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import CombustionConnectionGatedEntity


class CombustionSilenceButton(CombustionConnectionGatedEntity, ButtonEntity):
    """Silence any active alarms on the probe."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, connection_manager, control_manager, device_data) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._control = control_manager
        self._attr_unique_id = f"{device_data.serial_number}--silence-alarms"

    @property
    def name(self):
        """Entity name."""
        return "Silence alarms"

    async def async_press(self) -> None:
        """Send the silence-alarms command."""
        await self._control.async_silence(self._serial)


class CombustionResetProbeButton(CombustionConnectionGatedEntity, ButtonEntity):
    """Reset the thermometer, wiping the current cook session.

    Disabled by default: this is destructive and easy to press by accident,
    so it should be explicitly opted into rather than showing up unprompted.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, connection_manager, control_manager, device_data) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._control = control_manager
        self._attr_unique_id = f"{device_data.serial_number}--reset-thermometer"

    @property
    def name(self):
        """Entity name."""
        return "Reset thermometer"

    async def async_press(self) -> None:
        """Send the reset-probe command."""
        await self._control.async_reset_probe(self._serial)


class CombustionResetFoodSafeButton(CombustionConnectionGatedEntity, ButtonEntity):
    """Reset the Food Safe program state.

    Disabled by default: this is destructive and easy to press by accident,
    so it should be explicitly opted into rather than showing up unprompted.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, connection_manager, control_manager, device_data) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._control = control_manager
        self._attr_unique_id = f"{device_data.serial_number}--reset-food-safe"

    @property
    def name(self):
        """Entity name."""
        return "Reset food safe"

    async def async_press(self) -> None:
        """Send the reset-food-safe command."""
        await self._control.async_reset_food_safe(self._serial)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up button entities (only when active connection is enabled)."""
    probe_manager = hass.data[DOMAIN]
    if not getattr(probe_manager, "active_enabled", False):
        return
    conn = probe_manager.connection_manager
    control = probe_manager.control_manager

    def _create(probe_data):
        async_add_entities([
            CombustionSilenceButton(conn, control, probe_data),
            CombustionResetProbeButton(conn, control, probe_data),
            CombustionResetFoodSafeButton(conn, control, probe_data),
        ])

    conn.add_new_probe_listener(_create)
