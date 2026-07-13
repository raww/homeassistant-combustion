"""Hop Count."""
from enum import Enum


class HopCount(Enum):
    """Hop Count."""

    HOP1 = 0x00
    HOP2 = 0x01
    HOP3 = 0x02
    HOP4 = 0x03

    # Per the MeatNet node spec, hop count occupies bits 1-2 (LSB) of the
    # network information byte; bits 3-8 are reserved.
    HOP_COUNT_MASK = 0x3

    @staticmethod
    def from_network_info_byte(network_info_byte):
        """Generate hop count from network info byte."""
        raw_hop_count = network_info_byte & HopCount.HOP_COUNT_MASK.value
        return HopCount(raw_hop_count) if raw_hop_count in HopCount._value2member_map_ else HopCount.HOP1

    @staticmethod
    def default_values():
        """Generate default values."""
        return HopCount.HOP1
