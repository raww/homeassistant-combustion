"""Tests for the Combustion BLE probe high/low alarm UART command."""
from combustion.combustion_ble.uart import (
    CORE_SENSOR_INDEX,
    _alarm_word,
    set_probe_high_low_alarm,
)


def test_alarm_word_encoding():
    """An enabled alarm word packs raw13 temp (bits 3-15) with bit0 set.

    Note: the temperature bits are always encoded from ``temp_c``,
    regardless of ``enabled`` -- only bit0 (the enable flag) depends on it.
    A disabled word at 0.0C is therefore NOT the all-zero word; raw13 for
    0.0C is round((0.0 + 20.0) / 0.1) == 200 == 0x0C8, giving raw16 ==
    0x0640 and word bytes 40 06. This is confirmed by the CRC-verified
    reference frame in test_set_probe_high_low_alarm_core_high, whose low
    word (disabled, 0.0C) is exactly "4006".
    """
    assert _alarm_word(True, 95.0).hex() == "f123"
    assert _alarm_word(False, 0.0).hex() == "4006"


def test_set_probe_high_low_alarm_core_high():
    """Setting the core sensor's high alarm matches the reference frame."""
    frame = set_probe_high_low_alarm(CORE_SENSOR_INDEX, True, 95.0, False, 0.0)
    assert frame.hex() == (
        "cafea7270b2c00000000000000000000000000000000f123"
        "0000000000000000000000000000000000000000400600000000"
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


def test_alarm_clamps_temperature():
    """A very high temperature clamps raw13 to the 13-bit maximum."""
    word_bytes = _alarm_word(True, 1000.0)
    word = word_bytes[0] | (word_bytes[1] << 8)
    raw13 = (word >> 3) & 0x1FFF
    assert raw13 == 0x1FFF
