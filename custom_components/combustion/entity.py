"""CombustionEntity class."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DEVICE_NAME, DOMAIN, MANUFACTURER


class CombustionEntity(Entity):
    """CombustionEntity class."""

    _attr_should_poll = False

    def __init__(self, serial_number: str, device_name: str = DEVICE_NAME) -> None:
        """Initialize."""
        super().__init__()
        self._attr_device_info = DeviceInfo(
            name=f'{device_name} {serial_number}',
            identifiers={(DOMAIN, serial_number)},
            manufacturer=MANUFACTURER,
        )

    @property
    def available(self) -> bool:
        """Available while the device keeps advertising."""
        return self.probe_manager.device_available(self.device_serial_number)

    async def async_added_to_hass(self) -> None:
        """Register for updates once the entity is actually part of hass.

        Registering here (and unsubscribing via async_on_remove) guarantees a
        listener can never outlive its entity: entities whose platform add
        fails, or which are removed, stop receiving updates. Registering at
        construction time instead leaks listeners whenever entity creation is
        retried, which snowballs into an event storm.
        """
        await super().async_added_to_hass()
        self.async_on_remove(self.probe_manager.add_update_listener(self.on_update))
