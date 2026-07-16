"""Maintain a GATT connection to predictive probes and read predictions.

Prediction data (ready-in ETA, setpoint, estimated core) is only available
over a connection to the probe's Probe Status characteristic. This requires a
*connectable* bluetooth path — a local adapter or an ESPHome active proxy;
passive proxies (Shelly) cannot provide it.

Opt-in only: nothing here runs unless the "predictions" option is enabled.
"""
from __future__ import annotations

import asyncio
import contextlib

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from custom_components.combustion.combustion_ble.combustion_probe_data import (
    CombustionProbeData,
)
from custom_components.combustion.combustion_ble.prediction_data import PredictionData
from custom_components.combustion.const import BT_MANUFACTURER_ID, LOGGER
from custom_components.combustion.probe_manager import ProbeManager

_LOGGER = LOGGER.getChild('prediction')

PROBE_STATUS_CHAR = "00000101-caab-3792-3d44-97ae51c1407a"

RECONNECT_MIN_SECONDS = 5
RECONNECT_MAX_SECONDS = 300


class PredictionManager:
    """Connect to predictive probes and surface their prediction data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, probe_manager: ProbeManager, enabled: bool) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.probe_manager = probe_manager
        self.enabled = enabled
        self.data: dict[str, PredictionData] = {}
        self._create_sensors_callback = None
        self._listeners = []
        self._addresses: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._known: set[str] = set()

    def init_sensor_platform(self, create_sensors_callback):
        """Register the callback used to add prediction entities."""
        self._create_sensors_callback = create_sensors_callback

    def async_init(self) -> None:
        """Start listening for connectable probes (only when enabled)."""
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
            _LOGGER.warning("Could not register connectable bluetooth callback; predictions disabled", exc_info=True)
            return
        self.entry.async_on_unload(self._async_shutdown)

    def add_update_listener(self, listener):
        """Add listener to be notified of prediction updates.

        Returns a callable that removes the listener again.
        """
        self._listeners.append(listener)

        def _remove():
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    def prediction(self, serial_number: str) -> PredictionData | None:
        """Latest prediction for a probe serial, if any."""
        return self.data.get(serial_number)

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
                self.hass, self._maintain_connection(serial), f"combustion-prediction-{serial}"
            )

    async def _maintain_connection(self, serial: str) -> None:
        """Keep a connection open to one probe, reconnecting with backoff."""
        from bleak import BleakClient
        from bleak_retry_connector import establish_connection

        backoff = RECONNECT_MIN_SECONDS
        while True:
            address = self._addresses.get(serial)
            ble_device = bluetooth.async_ble_device_from_address(self.hass, address, connectable=True) if address else None
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
                await client.start_notify(PROBE_STATUS_CHAR, self._make_handler(serial))
                _LOGGER.debug("Connected to probe [%s] for predictions", serial)
                await disconnected.wait()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Prediction connection to [%s] failed", serial, exc_info=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)
            finally:
                if client is not None:
                    with contextlib.suppress(Exception):
                        await client.disconnect()

    def _make_handler(self, serial: str):
        @callback
        def handler(_char, data: bytearray) -> None:
            prediction = PredictionData.from_status_characteristic(bytes(data))
            if prediction is None:
                return
            self.data[serial] = prediction

            if serial not in self._known and self._create_sensors_callback is not None:
                self._known.add(serial)
                self._create_sensors_callback(self, serial)

            for listener in list(self._listeners):
                listener()

        return handler

    async def _async_shutdown(self) -> None:
        """Cancel all connection tasks on unload."""
        self._listeners.clear()
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
