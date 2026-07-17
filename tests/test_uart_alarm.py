"""Tests for the Combustion BLE probe high/low alarm UART command."""
from combustion.combustion_ble.uart import (
    CORE_SENSOR_INDEX,
    _alarm_word,
    set_probe_high_low_alarm,
)


def test_alarm_word_encoding():
    """An enabled alarm word packs raw13 temp (bits 3-15) with bit0 set.

    A disabled alarm always encodes as the all-zero canonical unset word,
    regardless of the temperature argument -- the device ignores the
    threshold bits when the enable bit is clear.
    """
    assert _alarm_word(True, 95.0).hex() == "f123"
    assert _alarm_word(False, 0.0).hex() == "0000"
    assert _alarm_word(False, 40.0).hex() == "0000"


def test_set_probe_high_low_alarm_core_high():
    """Setting the core sensor's high alarm matches the reference frame."""
    frame = set_probe_high_low_alarm(CORE_SENSOR_INDEX, True, 95.0, False, 0.0)
    assert frame.hex() == (
        "cafe32800b2c00000000000000000000000000000000f123"
        "0000000000000000000000000000000000000000000000000000"
    )

    payload = frame[6:]
    assert len(payload) == 44

    # Decode the core sensor's high word back to temperature and flag.
    high_offset = 6 + CORE_SENSOR_INDEX * 2
    word = frame[high_offset] | (frame[high_offset + 1] << 8)
    raw13 = (word >> 3) & 0x1FFF
    temp_c = raw13 * 0.1 - 20
    set_bit = word & 1
    assert temp_c == 95.0
    assert set_bit == 1


def test_set_probe_high_low_alarm_core_high_and_low():
    """Setting both the core sensor's high and low alarms matches the reference frame."""
    frame = set_probe_high_low_alarm(CORE_SENSOR_INDEX, True, 95.0, True, 40.0)
    assert frame.hex() == (
        "cafe7b3b0b2c00000000000000000000000000000000f123"
        "0000000000000000000000000000000000000000c11200000000"
    )


def test_alarm_clamps_temperature():
    """A very high temperature clamps raw13 to the 13-bit maximum."""
    word_bytes = _alarm_word(True, 1000.0)
    word = word_bytes[0] | (word_bytes[1] << 8)
    raw13 = (word >> 3) & 0x1FFF
    assert raw13 == 0x1FFF
