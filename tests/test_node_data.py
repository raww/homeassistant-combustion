"""Tests for MeatNet repeater (Booster/Display) self-advertisement parsing."""
from combustion.combustion_ble.node_data import NodeData


class _ServiceInfo:
    """Minimal stand-in for BluetoothServiceInfoBleak."""

    def __init__(self, payload: bytes, rssi: int = -70, address: str = 'aa:bb:cc:dd:ee:ff'):
        self.manufacturer_data = {2503: payload}
        self.rssi = rssi
        self.address = address


def _payload(product_type: int, serial: str = 'CR100040A8', prefs: int = 0x00) -> bytes:
    body = bytes([product_type]) + serial.encode('ascii') + bytes([prefs])
    return body + bytes(4)  # trailing bytes are ignored


def test_parses_booster():
    """A booster self-advert yields a BOOSTER node with its serial and RSSI."""
    node = NodeData.from_advertisement(_ServiceInfo(_payload(0x05)))
    assert node is not None
    assert node.valid
    assert node.device_type == 'BOOSTER'
    assert node.serial_number == 'CR100040A8'
    assert node.high_radio_power is False
    assert node.rssi == -70
    assert node.address == 'aa:bb:cc:dd:ee:ff'


def test_parses_display():
    """A display self-advert yields a DISPLAY node."""
    node = NodeData.from_advertisement(_ServiceInfo(_payload(0x04, serial='DP12345678')))
    assert node is not None
    assert node.device_type == 'DISPLAY'
    assert node.serial_number == 'DP12345678'


def test_high_radio_power_bit():
    """The low bit of the preferences byte sets high radio power."""
    node = NodeData.from_advertisement(_ServiceInfo(_payload(0x05, prefs=0x01)))
    assert node.high_radio_power is True


def test_ignores_non_node_product_types():
    """Non-repeater product types are not parsed as nodes."""
    # Probe (1), MeatNet node (2), Gauge (3), Engine (6) are not repeater self-adverts.
    for product_type in (0x00, 0x01, 0x02, 0x03, 0x06):
        assert NodeData.from_advertisement(_ServiceInfo(_payload(product_type))) is None


def test_rejects_short_payload():
    """A payload too short to hold a serial is rejected."""
    assert NodeData.from_advertisement(_ServiceInfo(bytes([0x05, 0x43, 0x52]))) is None


def test_rejects_empty_serial():
    """A node advert with an all-zero serial is rejected."""
    payload = bytes([0x05]) + bytes(10) + bytes([0x00])
    assert NodeData.from_advertisement(_ServiceInfo(payload)) is None


def test_missing_manufacturer_data():
    """Missing Combustion manufacturer data yields None."""
    info = _ServiceInfo(b'')
    info.manufacturer_data = {}
    assert NodeData.from_advertisement(info) is None
