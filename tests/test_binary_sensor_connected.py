"""Tests for the Connected diagnostic binary sensor."""
from combustion.binary_sensor import CombustionConnectedSensor


class _Conn:
    """Fake ConnectionManager exposing only what the sensor needs."""

    def __init__(self, connected):
        """Initialize with a fixed connection state."""
        self._c = connected
        self.listeners = []

    def is_connected(self, serial):
        """Return the fixed connection state."""
        return self._c

    def add_connection_listener(self, listener):
        """Record the listener and return a no-op remover."""
        self.listeners.append(listener)
        return lambda: None


class _DeviceData:
    """Fake device data with the attributes the entity reads."""

    serial_number = "S1"
    device_type = "PROBE"


def test_connected_reflects_state():
    """is_on mirrors ConnectionManager.is_connected."""
    ent = CombustionConnectedSensor(_Conn(True), _DeviceData())
    assert ent.is_on is True
    ent2 = CombustionConnectedSensor(_Conn(False), _DeviceData())
    assert ent2.is_on is False


def test_connected_always_available():
    """The sensor stays available even when disconnected, to report that state."""
    ent = CombustionConnectedSensor(_Conn(False), _DeviceData())
    assert ent.available is True
