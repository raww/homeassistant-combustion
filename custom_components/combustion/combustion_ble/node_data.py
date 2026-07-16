"""Parser for Combustion MeatNet repeater self-advertisements.

Boosters (product type 5) and Displays (product type 4) interleave their own
device-info advertisement between the repeated probe advertisements. That
self-advertisement carries only the node serial and a preferences byte; see
booster_ble_specification.rst / display_ble_specification.rst.
"""
from __future__ import annotations

from typing import NamedTuple

from custom_components.combustion.const import LOGGER

# manufacturer_data payload (no vendor prefix): type(1) serial(10) prefs(1) ...
NODE_SERIAL_RANGE = slice(1, 11)
NODE_PREFERENCES_INDEX = 11
NODE_MIN_LENGTH = 12

NODE_TYPE_NAMES = {0x04: 'DISPLAY', 0x05: 'BOOSTER'}


class NodeData(NamedTuple):
    """A MeatNet repeater's own advertisement."""

    device_type: str          # 'BOOSTER' or 'DISPLAY'
    serial_number: str
    high_radio_power: bool
    rssi: int
    address: str

    @property
    def valid(self) -> bool:
        """Whether the node advertisement carried a usable serial."""
        return bool(self.serial_number)

    @staticmethod
    def from_advertisement(service_info) -> NodeData | None:
        """Create instance from a repeater self-advertisement, or None."""
        from custom_components.combustion.const import BT_MANUFACTURER_ID

        payload = service_info.manufacturer_data.get(BT_MANUFACTURER_ID)
        if not payload or len(payload) < NODE_MIN_LENGTH:
            return None
        product_type = payload[0]
        name = NODE_TYPE_NAMES.get(product_type)
        if name is None:
            return None

        serial = bytes(payload[NODE_SERIAL_RANGE]).rstrip(b'\x00 ').decode('ascii', errors='replace')
        if not serial:
            LOGGER.debug("Ignoring %s advertisement with empty serial", name)
            return None
        high_radio_power = bool(payload[NODE_PREFERENCES_INDEX] & 0x01)

        return NodeData(
            device_type=name,
            serial_number=serial,
            high_radio_power=high_radio_power,
            rssi=service_info.rssi,
            address=service_info.address,
        )
