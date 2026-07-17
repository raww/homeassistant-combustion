"""Tests for the shared BLE ConnectionManager."""
import pytest
from combustion.connection_manager import ConnectionManager
from homeassistant.exceptions import HomeAssistantError


class _FakeClient:
    """Minimal stand-in for a bleak BleakClient."""

    def __init__(self):
        """Initialize with empty notification/write records."""
        self.notifications = {}
        self.written = []
        self.connected = True

    async def start_notify(self, char, handler):
        """Record the notify handler registered for a characteristic."""
        self.notifications[char] = handler

    async def write_gatt_char(self, char, data, response=True):
        """Record a GATT write."""
        self.written.append((char, bytes(data)))

    async def disconnect(self):
        """Mark the fake client as disconnected."""
        self.connected = False


def _manager(hass):
    from unittest.mock import MagicMock
    entry = MagicMock()
    entry.async_on_unload = MagicMock()
    pm = MagicMock()
    return ConnectionManager(hass, entry, pm, enabled=True)


@pytest.mark.asyncio
async def test_subscribe_registers_handler_on_connect(hass):
    """A subscribed char gets start_notify called when a client connects."""
    mgr = _manager(hass)
    seen = []
    mgr.subscribe("char-a", lambda serial, data: seen.append((serial, data)))
    client = _FakeClient()
    await mgr._on_connected("SERIAL1", client)
    assert "char-a" in client.notifications
    # a notification routes to the handler with the serial
    client.notifications["char-a"](None, bytearray(b"\x01\x02"))
    assert seen == [("SERIAL1", b"\x01\x02")]


@pytest.mark.asyncio
async def test_send_command_writes_when_connected(hass):
    """async_send_command writes the frame to the UART RX char."""
    mgr = _manager(hass)
    client = _FakeClient()
    await mgr._on_connected("SERIAL1", client)
    frame = b"\xca\xfe\x00\x00\x0c\x00"
    await mgr.async_send_command("SERIAL1", frame)
    assert client.written[0] == (ConnectionManager.UART_RX_CHAR, frame)


@pytest.mark.asyncio
async def test_send_command_raises_when_not_connected(hass):
    """async_send_command raises when the probe has no live client or address."""
    mgr = _manager(hass)
    with pytest.raises(HomeAssistantError):
        await mgr.async_send_command("UNKNOWN", b"\xca\xfe\x00\x00\x0c\x00")


@pytest.mark.asyncio
async def test_connection_listener_fires_on_state_change(hass):
    """Connect/disconnect notifies connection listeners and flips is_connected."""
    mgr = _manager(hass)
    ticks = []
    mgr.add_connection_listener(lambda: ticks.append(mgr.is_connected("SERIAL1")))
    await mgr._on_connected("SERIAL1", _FakeClient())
    assert mgr.is_connected("SERIAL1") is True
    mgr._on_disconnected("SERIAL1")
    assert mgr.is_connected("SERIAL1") is False
    assert ticks == [True, False]


@pytest.mark.asyncio
async def test_new_probe_listener_fires_once_on_first_connect(hass):
    """A new-probe listener fires once on first connect, not on reconnect, and immediately for late registrants."""
    mgr = _manager(hass)
    probe_data = object()
    mgr._probe_data["S1"] = probe_data

    seen = []
    mgr.add_new_probe_listener(seen.append)

    await mgr._on_connected("S1", _FakeClient())
    assert seen == [probe_data]

    # a second connect for the same serial (e.g. reconnect) must not re-fire
    await mgr._on_connected("S1", _FakeClient())
    assert seen == [probe_data]

    # a listener registered after the probe was already seen fires immediately
    late_seen = []
    mgr.add_new_probe_listener(late_seen.append)
    assert late_seen == [probe_data]
