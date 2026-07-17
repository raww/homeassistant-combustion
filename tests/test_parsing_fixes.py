"""Unit tests for parsing fixes verified against the Combustion reference SDKs."""
from combustion.combustion_ble.hop_count import HopCount
from combustion.combustion_ble.probe_temperatures import ProbeTemperatures


def test_overheating_indices_thresholds():
    """Each thermistor trips at its reference threshold (T1/2=105, T3=115, T4=125, T5-8=315.56)."""
    # T2 (idx1), T4 (idx3), T6 (idx5), T8 (idx7) over their thresholds.
    temps = [20.0, 110.0, 22.0, 130.0, 24.0, 320.0, 26.0, 320.0]
    assert ProbeTemperatures(temps).overheating_indices() == [1, 3, 5, 7]


def test_overheating_none_when_below_thresholds():
    """No sensor is overheating for ordinary cooking temperatures."""
    temps = [20.0, 21.1, 22.2, 23.3, 24.4, 25.5, 26.6, 27.7]
    assert ProbeTemperatures(temps).overheating_indices() == []


def test_overheating_is_inclusive_at_threshold():
    """A thermistor exactly at its threshold counts as overheating (>=)."""
    temps = [105.0, 0.0, 115.0, 125.0, 315.56, 0.0, 0.0, 0.0]
    assert ProbeTemperatures(temps).overheating_indices() == [0, 2, 3, 4]


def test_hop_count_uses_top_two_bits():
    """Hop count is (byte >> 6) & 0x3, per both shipped SDKs (not the low bits)."""
    assert HopCount.from_network_info_byte(0x00) is HopCount.HOP1
    assert HopCount.from_network_info_byte(0x40) is HopCount.HOP2
    assert HopCount.from_network_info_byte(0x80) is HopCount.HOP3
    assert HopCount.from_network_info_byte(0xC0) is HopCount.HOP4
    # Low bits are reserved and must not affect the hop count.
    assert HopCount.from_network_info_byte(0x3F) is HopCount.HOP1
