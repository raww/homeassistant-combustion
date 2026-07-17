"""CombustionEntity class."""
from __future__ import annotations

from homeassistant.core import callback
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


class CombustionConnectionGatedEntity(CombustionEntity):
    """Shared lifecycle for control entities gated on BLE connection state.

    Control entities (number/select platforms) have no `probe_manager`; their
    availability and state instead track the `ConnectionManager`'s
    connect/disconnect events. Consolidating that lifecycle here means a
    future control entity picks it up automatically instead of re-copying it
    (and risking the crash described in `async_added_to_hass` below).
    """

    def __init__(self, connection_manager, device_data, device_name: str = DEVICE_NAME) -> None:
        """Initialize, storing the connection manager and target serial."""
        super().__init__(device_data.serial_number, device_name)
        self._conn = connection_manager
        self._serial = device_data.serial_number
        self.device_serial_number = device_data.serial_number

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
