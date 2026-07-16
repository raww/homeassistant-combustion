"""Combustion BLE UART message framing.

Request:  CA FE | CRC(2, LE) | type(1) | len(1) | payload
Response: CA FE | CRC(2, LE) | type(1) | success(1) | len(1) | payload

CRC is CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no xorout)
over type + len + payload (request) or type + success + len + payload (response).
Verified against combustion-inc/combustion-android-ble.
"""
from __future__ import annotations

from typing import NamedTuple

SYNC = bytes([0xCA, 0xFE])
REQUEST_HEADER_SIZE = 6
RESPONSE_HEADER_SIZE = 7


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
