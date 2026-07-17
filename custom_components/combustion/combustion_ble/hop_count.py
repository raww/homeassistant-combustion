"""Hop Count."""
from enum import Enum


class HopCount(Enum):
    """Hop Count."""

    HOP1 = 0x00
    HOP2 = 0x01
    HOP3 = 0x02
    HOP4 = 0x03

    # Hop count occupies the top 2 bits (bits 7-8) of the network information
    # byte: value = (byte >> 6) & 0x3. This matches both shipped Combustion
    # SDKs (iOS HOP_COUNT_SHIFT = 6, Android identical). (HOP_COUNT_MASK aliases
    # HOP4 since both are 0x3, so .value is 3.)
    HOP_COUNT_MASK = 0x3

    @staticmethod
    def from_network_info_byte(network_info_byte):
        """Generate hop count from network info byte."""
        raw_hop_count = (network_info_byte >> 6) & HopCount.HOP_COUNT_MASK.value
        return HopCount(raw_hop_count) if raw_hop_count in HopCount._value2member_map_ else HopCount.HOP1

    @staticmethod
    def default_values():
        """Generate default values."""
        return HopCount.HOP1
