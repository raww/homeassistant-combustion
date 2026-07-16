"""Tests for the Combustion BLE UART framing."""
from combustion.combustion_ble.uart import (
    build_request,
    crc16_ccitt,
    parse_response,
)


def test_crc_check_value():
    """CRC-16/CCITT-FALSE check string yields 0x29B1."""
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_build_request_set_prediction_vector():
    """Set Prediction 60.0C / mode 2 matches the reference frame."""
    # payload = little-endian uint16 of (600 & 0x3FF) | (2 << 10) = 0x0A58
    frame = build_request(0x05, bytes([0x58, 0x0A]))
    assert frame.hex() == "cafeb9700502580a"


def test_build_request_zero_payload():
    """A no-payload command (silence, 0x0C) frames correctly."""
    assert build_request(0x0C, b"").hex() == "cafe62580c00"


def test_parse_response_roundtrip_success():
    """A well-formed success response parses back to its fields."""
    # Build a response frame: CA FE crc type success len payload
    payload = bytes([0x11, 0x22])
    body = bytes([0x05, 0x01, len(payload)]) + payload  # type, success=1, len, payload
    crc = crc16_ccitt(body)
    frame = bytes([0xCA, 0xFE, crc & 0xFF, (crc >> 8) & 0xFF]) + body
    resp = parse_response(frame)
    assert resp is not None
    assert resp.msg_type == 0x05
    assert resp.success is True
    assert resp.payload == payload


def test_parse_response_rejects_bad_sync():
    """A frame without the CA FE sync is rejected."""
    assert parse_response(bytes([0x00, 0x00, 0, 0, 5, 1, 0])) is None


def test_parse_response_rejects_bad_crc():
    """A frame whose CRC does not match is rejected."""
    body = bytes([0x05, 0x01, 0x00])
    frame = bytes([0xCA, 0xFE, 0x00, 0x00]) + body  # deliberately wrong CRC
    assert parse_response(frame) is None


def test_set_prediction_packs_setpoint_and_mode():
    """Set Prediction packs setpoint (0.1C, 10-bit) | mode << 10, LE."""
    from combustion.combustion_ble.uart import PredictionMode, set_prediction
    frame = set_prediction(60.0, PredictionMode.REMOVAL_AND_RESTING)
    assert frame.hex() == "cafeb9700502580a"


def test_set_prediction_clamps_setpoint():
    """Setpoints above 102.3C clamp to the 10-bit maximum."""
    from combustion.combustion_ble.uart import PredictionMode, set_prediction
    frame = set_prediction(200.0, PredictionMode.NONE)
    # payload word low 10 bits == 0x3FF
    word = frame[6] | (frame[7] << 8)
    assert (word & 0x3FF) == 0x3FF


def test_silence_alarms_frame():
    """Silence alarms is a no-payload 0x0C command."""
    from combustion.combustion_ble.uart import silence_alarms
    assert silence_alarms().hex() == "cafe62580c00"


def test_set_power_mode_payload():
    """Set Power Mode carries a single mode byte."""
    from combustion.combustion_ble.uart import PowerMode, set_power_mode
    frame = set_power_mode(PowerMode.ALWAYS_ON)
    assert frame[4] == 0x09 and frame[5] == 0x01 and frame[6] == 0x01


def test_set_probe_id_and_colour_payload():
    """Set Probe ID / Colour carry a single 0-7 byte."""
    from combustion.combustion_ble.uart import set_probe_colour, set_probe_id
    assert set_probe_id(3)[4] == 0x01 and set_probe_id(3)[6] == 0x03
    assert set_probe_colour(5)[4] == 0x02 and set_probe_colour(5)[6] == 0x05


def test_reset_commands_have_no_payload():
    """Reset probe / food safe are no-payload commands."""
    from combustion.combustion_ble.uart import reset_food_safe, reset_probe
    assert reset_probe()[4] == 0x0A and reset_probe()[5] == 0x00
    assert reset_food_safe()[4] == 0x08 and reset_food_safe()[5] == 0x00
