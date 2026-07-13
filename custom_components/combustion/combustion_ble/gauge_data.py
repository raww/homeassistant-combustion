"""Parser for Combustion Gauge BLE advertisements.

See https://github.com/combustion-inc/combustion-documentation
(gauge_ble_specification.rst).
"""
from __future__ import annotations

from typing import NamedTuple

from custom_components.combustion.const import LOGGER

# Advertising payload layout, offsets relative to vendor-prefixed data:
#   [0:2]   Vendor ID (0x09C7, big endian)
#   [2]     Product Type (Gauge = 3)
#   [3:13]  Serial number (10 bytes, alphanumeric)
#   [13:15] Raw temperature data (13-bit packed, 0.1C resolution)
#   [15]    Gauge status flags
#   [16]    Reserved
#   [17:21] High-Low alarm status
#   [21]    Gauge preferences
GAUGE_PAYLOAD_MIN_LENGTH = 21


class GaugeAlarm(NamedTuple):
    """A single high or low alarm status."""

    is_set: bool
    tripped: bool
    alarming: bool
    temperature: float

    @staticmethod
    def from_raw(raw: int) -> GaugeAlarm:
        """Create instance from a packed 16-bit alarm status."""
        return GaugeAlarm(
            is_set=bool(raw & 0x1),
            tripped=bool(raw & 0x2),
            alarming=bool(raw & 0x4),
            temperature=((raw >> 3) & 0x1FFF) * 0.1 - 20.0,
        )


class GaugeData(NamedTuple):
    """Parsed Gauge advertisement."""

    serial_number: str
    sensor_present: bool
    sensor_overheating: bool
    battery_low: bool
    temperature: float | None
    high_alarm: GaugeAlarm
    low_alarm: GaugeAlarm

    @staticmethod
    def from_data(data: bytes) -> GaugeData | None:
        """Create instance from vendor-prefixed raw advertising data."""
        if data is None or len(data) < GAUGE_PAYLOAD_MIN_LENGTH:
            LOGGER.debug("Not constructing Gauge data; payload too short [%s]", len(data) if data else None)
            return None

        serial_number = bytes(data[3:13]).rstrip(b'\x00 ').decode('ascii', errors='replace')
        if not serial_number:
            return None

        flags = data[15]
        sensor_present = bool(flags & 0x1)
        sensor_overheating = bool(flags & 0x2)
        battery_low = bool(flags & 0x4)

        raw_temperature = int.from_bytes(data[13:15], byteorder='little') & 0x1FFF
        # Per spec the temperature value is meaningless while no sensor is attached.
        temperature = (raw_temperature * 0.1 - 20.0) if sensor_present else None

        alarm_status = int.from_bytes(data[17:21], byteorder='little')
        high_alarm = GaugeAlarm.from_raw(alarm_status & 0xFFFF)
        low_alarm = GaugeAlarm.from_raw((alarm_status >> 16) & 0xFFFF)

        return GaugeData(
            serial_number=serial_number,
            sensor_present=sensor_present,
            sensor_overheating=sensor_overheating,
            battery_low=battery_low,
            temperature=temperature,
            high_alarm=high_alarm,
            low_alarm=low_alarm,
        )


class CombustionGaugeData:
    """Data for a Combustion Gauge, as consumed by the entity platforms."""

    def __init__(self, gauge_data: GaugeData, rssi: int, address: str) -> None:
        """Initialize the class."""
        self.gauge_data = gauge_data
        self._rssi = rssi
        self._address = address

    @property
    def valid(self) -> bool:
        """Determine if the gauge data is valid."""
        return bool(self.gauge_data.serial_number)

    @property
    def address(self) -> str:
        """The address of the device which sent the advertising payload."""
        return self._address

    @property
    def device_type(self) -> str:
        """Type of device which sent the advertising payload."""
        return 'GAUGE'

    @property
    def rssi(self) -> int:
        """Signal strength."""
        return self._rssi

    @property
    def serial_number(self) -> str:
        """Serial number of the gauge."""
        return self.gauge_data.serial_number

    @property
    def battery_ok(self) -> bool:
        """Battery state."""
        return not self.gauge_data.battery_low

    @property
    def temperature(self):
        """Gauge temperature, or None when no sensor is attached."""
        return self.gauge_data.temperature

    @property
    def sensor_present(self) -> bool:
        """Whether the gauge's temperature sensor is attached."""
        return self.gauge_data.sensor_present

    @property
    def sensor_overheating(self) -> bool:
        """Whether the gauge's temperature sensor is overheating."""
        return self.gauge_data.sensor_overheating

    @property
    def high_alarm(self) -> GaugeAlarm:
        """High alarm status."""
        return self.gauge_data.high_alarm

    @property
    def low_alarm(self) -> GaugeAlarm:
        """Low alarm status."""
        return self.gauge_data.low_alarm

    @staticmethod
    def from_advertisement(service_info) -> CombustionGaugeData | None:
        """Create instance from BT advertisement data."""
        from custom_components.combustion.const import BT_MANUFACTURER_ID

        vendor_id = 0x09C7.to_bytes(2, 'big')
        data = vendor_id + service_info.manufacturer_data[BT_MANUFACTURER_ID]
        gauge_data = GaugeData.from_data(data)
        if gauge_data is None:
            return None
        return CombustionGaugeData(gauge_data, service_info.rssi, service_info.address)
