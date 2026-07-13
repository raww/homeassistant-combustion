"""Bluetooth Advertising Data."""

from enum import Enum
from typing import NamedTuple, Optional

from custom_components.combustion.const import LOGGER

from .battery_status_virtual_sensors import BatteryStatusVirtualSensors
from .hop_count import HopCount
from .mode_id import ModeId
from .probe_temperatures import ProbeTemperatures


class CombustionProductType(Enum):
    """Combustion Product Type.

    See https://github.com/combustion-inc/combustion-documentation
    (meatnet_node_ble_specification.rst, "Product Type").
    """

    UNKNOWN = 0x00
    PROBE = 0x01
    MEAT_NET_NODE = 0x02
    GAUGE = 0x03
    DISPLAY = 0x04
    BOOSTER = 0x05
    ENGINE = 0x06

    @classmethod
    def from_byte(cls, byte: int) -> 'CombustionProductType':
        """Create instance from a raw byte, tolerating future product types."""
        try:
            return cls(byte)
        except ValueError:
            return cls.UNKNOWN


class AdvertisingData(NamedTuple):
    """Bluetooth Advertising Data."""

    type: CombustionProductType
    serial_number: int
    temperatures: ProbeTemperatures
    mode_id: ModeId
    battery_status_virtual_sensors: BatteryStatusVirtualSensors
    hop_count: HopCount

    @staticmethod
    def from_data(data: bytes) -> Optional['AdvertisingData']:
        """Create instance from raw advertising data."""
        if data is None or len(data) < 20:
            LOGGER.debug('Not constructing Advertising data because [%s] != 20', len(data) if data else None)
            return None

        # Vendor ID
        vendor_id = int.from_bytes(data[0:2], byteorder='big')
        if vendor_id != 0x09C7:
            LOGGER.debug("Not constructing Advertising data because [%s] != 0x09C7", vendor_id)
            return None

        # Product type
        product_type = CombustionProductType.from_byte(data[2])
        if product_type not in (CombustionProductType.PROBE, CombustionProductType.MEAT_NET_NODE):
            # Only probe advertisements (direct or repeated by a MeatNet node)
            # carry the probe payload parsed below.
            return None

        # Serial number
        serial_number = int.from_bytes(data[3:7], byteorder='little')

        # Temperatures
        temperatures = ProbeTemperatures.from_raw_data(data[7:20])

        # ModeId
        mode_id = ModeId.from_byte(data[20]) if len(data) >= 21 else ModeId.default_values()

        # Battery Status and Virtual Sensors
        battery_status_virtual_sensors = BatteryStatusVirtualSensors.from_byte(data[21]) if len(data) >= 22 else BatteryStatusVirtualSensors.default_values()

        # Hop Count
        hop_count = HopCount.from_network_info_byte(data[22]) if len(data) >= 23 else HopCount.default_values()

        return AdvertisingData(type=product_type, serial_number=serial_number, temperatures=temperatures, mode_id=mode_id, battery_status_virtual_sensors=battery_status_virtual_sensors, hop_count=hop_count)
