"""Own per-probe connectable BLE connections; shared by predictions and control.

Requires a *connectable* path (local adapter or ESPHome active proxy). Passive
proxies cannot provide it. Opt-in via the active-connection option.
"""
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from custom_components.combustion.combustion_ble.combustion_probe_data import (
    CombustionProbeData,
)
from custom_components.combustion.const import BT_MANUFACTURER_ID, LOGGER
from custom_components.combustion.probe_manager import ProbeManager

_LOGGER = LOGGER.getChild('connection')

RECONNECT_MIN_SECONDS = 5
RECONNECT_MAX_SECONDS = 300
WRITE_TIMEOUT = 5.0


class ConnectionManager:
    """Maintain connectable probe connections and expose subscribe/send seams."""

    UART_RX_CHAR = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, probe_manager: ProbeManager, enabled: bool
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.probe_manager = probe_manager
        self.enabled = enabled
        self._subscriptions: dict[str, Callable] = {}
        self._clients: dict[str, object] = {}
        self._addresses: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._conn_listeners: list[Callable] = []

    def async_init(self) -> None:
        """Register the connectable advert callback (only when enabled)."""
        if not self.enabled:
            return
        try:
            self.entry.async_on_unload(
                bluetooth.async_register_callback(
                    self.hass,
                    self._connectable_advertisement,
                    bluetooth.BluetoothCallbackMatcher(manufacturer_id=BT_MANUFACTURER_ID, connectable=True),
                    bluetooth.BluetoothScanningMode.ACTIVE,
                )
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Could not register connectable callback; active connection disabled", exc_info=True)
            return
        self.entry.async_on_unload(self._async_shutdown)

    def subscribe(self, char_uuid: str, handler: Callable) -> None:
        """Register a notify handler `(serial, data: bytes)` for a characteristic."""
        self._subscriptions[char_uuid] = handler

    def add_connection_listener(self, listener: Callable) -> Callable:
        """Register a listener called on any connect/disconnect. Returns remover."""
        self._conn_listeners.append(listener)

        def _remove():
            if listener in self._conn_listeners:
                self._conn_listeners.remove(listener)

        return _remove

    def is_connected(self, serial: str) -> bool:
        """Whether a live client exists for this probe serial."""
        return serial in self._clients

    def _notify_conn_listeners(self) -> None:
        for listener in list(self._conn_listeners):
            listener()

    @callback
    def _connectable_advertisement(self, service_info, change) -> None:
        """Handle a connectable probe advertisement by ensuring a connection."""
        payload = service_info.manufacturer_data.get(BT_MANUFACTURER_ID)
        if not payload or payload[0] != 0x01:
            return  # only direct probe advertisements are connectable probes
        try:
            probe_data = CombustionProbeData.from_advertisement(service_info)
        except Exception:  # noqa: BLE001
            return
        if probe_data is None or not probe_data.valid:
            return
        serial = probe_data.serial_number
        self._addresses[serial] = service_info.address
        task = self._tasks.get(serial)
        if task is None or task.done():
            self._tasks[serial] = self.entry.async_create_background_task(
                self.hass, self._maintain_connection(serial), f"combustion-conn-{serial}"
            )

    async def _maintain_connection(self, serial: str) -> None:
        """Keep a connection open to one probe, reconnecting with backoff."""
        from bleak import BleakClient
        from bleak_retry_connector import establish_connection

        backoff = RECONNECT_MIN_SECONDS
        while True:
            address = self._addresses.get(serial)
            ble_device = (
                bluetooth.async_ble_device_from_address(self.hass, address, connectable=True)
                if address
                else None
            )
            if ble_device is None:
                # no connectable path right now; wait and retry
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)
                continue

            disconnected = asyncio.Event()
            client = None
            try:
                client = await establish_connection(
                    BleakClient, ble_device, serial,
                    disconnected_callback=lambda _c, ev=disconnected: ev.set(),
                )
                backoff = RECONNECT_MIN_SECONDS
                await self._on_connected(serial, client)
                await disconnected.wait()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Connection to [%s] failed", serial, exc_info=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)
            finally:
                self._on_disconnected(serial)
                if client is not None:
                    with contextlib.suppress(Exception):
                        await client.disconnect()

    async def _on_connected(self, serial: str, client) -> None:
        """Record a live client and (re)subscribe all notify handlers."""
        self._clients[serial] = client
        for char, handler in self._subscriptions.items():
            with contextlib.suppress(Exception):
                await client.start_notify(char, self._make_notify(serial, handler))
        self._notify_conn_listeners()

    def _on_disconnected(self, serial: str) -> None:
        """Drop the live client and notify listeners."""
        if self._clients.pop(serial, None) is not None:
            self._notify_conn_listeners()

    def _make_notify(self, serial: str, handler: Callable) -> Callable:
        """Wrap a subscribed handler so it receives `(serial, data: bytes)`."""
        @callback
        def _cb(_char, data: bytearray) -> None:
            handler(serial, bytes(data))

        return _cb

    async def _write_and_wait(self, client, frame: bytes, expect: bool):
        """Write a frame to the UART RX char.

        `expect` is reserved for a future response-read seam; writes are
        currently fire-and-forget.
        """
        await client.write_gatt_char(self.UART_RX_CHAR, frame, response=True)
        return None

    async def async_send_command(self, serial: str, frame: bytes) -> None:
        """Write a UART command to a probe, raising if it is not connected."""
        client = self._clients.get(serial)
        if client is None:
            # try one on-demand connect if we know the address
            address = self._addresses.get(serial)
            if address is None:
                raise HomeAssistantError(f"{serial} is not connected")
            # ensure the maintain loop is running; give it a moment
            self._connectable_kick(serial)
            for _ in range(int(WRITE_TIMEOUT * 10)):
                await asyncio.sleep(0.1)
                client = self._clients.get(serial)
                if client is not None:
                    break
            if client is None:
                raise HomeAssistantError(f"{serial} is not connected")
        try:
            await self._write_and_wait(client, frame, expect=False)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to send command to {serial}: {err}") from err

    def _connectable_kick(self, serial: str) -> None:
        """Ensure the maintain loop for a serial is running."""
        task = self._tasks.get(serial)
        if task is None or task.done():
            self._tasks[serial] = self.entry.async_create_background_task(
                self.hass, self._maintain_connection(serial), f"combustion-conn-{serial}"
            )

    async def _async_shutdown(self) -> None:
        """Cancel all connection tasks on unload."""
        self._conn_listeners.clear()
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._clients.clear()
