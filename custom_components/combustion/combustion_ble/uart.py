"""Combustion BLE UART message framing.

Request:  CA FE | CRC(2, LE) | type(1) | len(1) | payload
Response: CA FE | CRC(2, LE) | type(1) | success(1) | len(1) | payload

CRC is CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no xorout)
over type + len + payload (request) or type + success + len + payload (response).
Verified against combustion-inc/combustion-android-ble.
"""
from __future__ import annotations

from enum import IntEnum
from typing import NamedTuple

SYNC = bytes([0xCA, 0xFE])
REQUEST_HEADER_SIZE = 6
RESPONSE_HEADER_SIZE = 7

# Index of the virtual "core" sensor within the 11-sensor alarm layout
# (T1-T8, then virtual core/surface/ambient).
CORE_SENSOR_INDEX = 8


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE over the given bytes."""
    crc = 0xFFFF
    for byte in data:
        for i in range(8):
            bit = (byte >> (7 - i)) & 1
            c15 = (crc >> 15) & 1
            crc = (crc << 1) & 0xFFFF
            if c15 ^ bit:
                crc ^= 0x1021
    return crc & 0xFFFF


def build_request(msg_type: int, payload: bytes) -> bytes:
    """Frame a request message with sync bytes and CRC."""
    body = bytes([msg_type, len(payload)]) + payload
    crc = crc16_ccitt(body)
    return SYNC + bytes([crc & 0xFF, (crc >> 8) & 0xFF]) + body


class Response(NamedTuple):
    """A parsed UART response message."""

    msg_type: int
    success: bool
    payload: bytes


def parse_response(data: bytes) -> Response | None:
    """Parse and validate a response frame, or None if malformed."""
    if len(data) < RESPONSE_HEADER_SIZE or data[0:2] != SYNC:
        return None
    msg_type = data[4]
    success = data[5] > 0
    length = data[6]
    if len(data) < RESPONSE_HEADER_SIZE + length:
        return None
    crc_body = data[4:7 + length]  # type + success + len + payload
    sent_crc = data[2] | (data[3] << 8)
    if crc16_ccitt(crc_body) != sent_crc:
        return None
    return Response(msg_type=msg_type, success=success, payload=bytes(data[7:7 + length]))


class MessageType(IntEnum):
    """UART request message type IDs."""

    SET_PROBE_ID = 0x01
    SET_PROBE_COLOR = 0x02
    SET_PREDICTION = 0x05
    RESET_FOOD_SAFE = 0x08
    SET_POWER_MODE = 0x09
    RESET_PROBE = 0x0A
    SET_PROBE_HIGH_LOW_ALARM = 0x0B
    SILENCE_PROBE_ALARMS = 0x0C


class PredictionMode(IntEnum):
    """Prediction input mode (2-bit field)."""

    NONE = 0
    TIME_TO_REMOVAL = 1
    REMOVAL_AND_RESTING = 2


class PowerMode(IntEnum):
    """Probe power mode."""

    NORMAL = 0
    ALWAYS_ON = 1


def parse_request_payload_word(frame: bytes) -> int:
    """Return the little-endian uint16 payload word of a request (test helper)."""
    return frame[6] | (frame[7] << 8)


def set_prediction(setpoint_c: float, mode: PredictionMode) -> bytes:
    """Build a Set Prediction command."""
    converted = int(round(setpoint_c * 10.0))
    clamped = min(max(converted, 0), 0x3FF)
    word = (clamped & 0x3FF) | (int(mode) << 10)
    payload = bytes([word & 0xFF, (word >> 8) & 0xFF])
    return build_request(MessageType.SET_PREDICTION, payload)


def silence_alarms() -> bytes:
    """Build a Silence Alarms command."""
    return build_request(MessageType.SILENCE_PROBE_ALARMS, b"")


def set_power_mode(mode: PowerMode) -> bytes:
    """Build a Set Power Mode command."""
    return build_request(MessageType.SET_POWER_MODE, bytes([int(mode)]))


def set_probe_id(probe_id: int) -> bytes:
    """Build a Set Probe ID command (0-7)."""
    return build_request(MessageType.SET_PROBE_ID, bytes([probe_id & 0x07]))


def set_probe_colour(colour: int) -> bytes:
    """Build a Set Probe Colour command (0-7)."""
    return build_request(MessageType.SET_PROBE_COLOR, bytes([colour & 0x07]))


def reset_probe() -> bytes:
    """Build a Reset Thermometer command (wipes the cook session)."""
    return build_request(MessageType.RESET_PROBE, b"")


def reset_food_safe() -> bytes:
    """Build a Reset Food Safe command."""
    return build_request(MessageType.RESET_FOOD_SAFE, b"")


def _alarm_word(enabled: bool, temp_c: float) -> bytes:
    """Build a 2-byte little-endian AlarmStatus word.

    Bits 3-15 of the 16-bit word hold the raw temperature,
    ``round((temp_c + 20.0) / 0.1)`` clamped to ``[0, 0x1FFF]``. Bit 0 of the
    low byte is set when the alarm is enabled; tripped (bit 1) and alarming
    (bit 2) are always 0 in a command.
    """
    raw13 = round((temp_c + 20.0) / 0.1)
    raw13 = min(max(raw13, 0), 0x1FFF)
    raw16 = (raw13 << 3) & 0xFFFF
    low_byte = (raw16 & 0xFF) | (0x01 if enabled else 0x00)
    high_byte = (raw16 >> 8) & 0xFF
    return bytes([low_byte, high_byte])


def set_probe_high_low_alarm(
    sensor_index: int,
    high_enabled: bool,
    high_temp_c: float,
    low_enabled: bool,
    low_temp_c: float,
) -> bytes:
    """Build a Set Probe High/Low Alarm command for one sensor (others left unset).

    The payload is a fixed 44-byte structure covering all 11 alarmable
    sensors (T1-T8, virtual core, surface, ambient): 11 high-alarm words
    followed by 11 low-alarm words, 2 bytes each. Only ``sensor_index``'s
    words are written; every other sensor's words stay zero (unset).
    """
    payload = bytearray(44)
    high_offset = sensor_index * 2
    low_offset = 22 + sensor_index * 2
    payload[high_offset:high_offset + 2] = _alarm_word(high_enabled, high_temp_c)
    payload[low_offset:low_offset + 2] = _alarm_word(low_enabled, low_temp_c)
    return build_request(MessageType.SET_PROBE_HIGH_LOW_ALARM, bytes(payload))
