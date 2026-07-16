"""Read predictions from probes over the shared connectable BLE connection.

Prediction data (ready-in ETA, setpoint, estimated core) is only available
over a connection to the probe's Probe Status characteristic. This requires a
*connectable* bluetooth path — a local adapter or an ESPHome active proxy;
passive proxies (Shelly) cannot provide it.

Opt-in only: nothing here runs unless the "predictions" option is enabled
(enforced by the shared ConnectionManager).
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.combustion.combustion_ble.prediction_data import PredictionData
from custom_components.combustion.connection_manager import ConnectionManager
from custom_components.combustion.const import LOGGER
from custom_components.combustion.probe_manager import ProbeManager

_LOGGER = LOGGER.getChild('prediction')

PROBE_STATUS_CHAR = "00000101-caab-3792-3d44-97ae51c1407a"


class PredictionManager:
    """Consume Probe Status notifications and surface their prediction data."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, connection_manager: ConnectionManager, probe_manager: ProbeManager
    ) -> None:
        """Initialize as a consumer of the shared connection."""
        self.hass = hass
        self.entry = entry
        self.connection_manager = connection_manager
        self.probe_manager = probe_manager
        self.data: dict[str, PredictionData] = {}
        self._create_sensors_callback = None
        self._listeners = []
        self._known: set[str] = set()

    def init_sensor_platform(self, create_sensors_callback):
        """Register the callback used to add prediction entities."""
        self._create_sensors_callback = create_sensors_callback

    def async_init(self) -> None:
        """Subscribe to the Probe Status characteristic on the shared connection."""
        self.connection_manager.subscribe(PROBE_STATUS_CHAR, self._on_status)

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

    def _on_status(self, serial: str, data: bytes) -> None:
        """Handle a Probe Status notification from the shared connection."""
        prediction = PredictionData.from_status_characteristic(data)
        if prediction is None:
            return
        self.data[serial] = prediction

        if serial not in self._known and self._create_sensors_callback is not None:
            self._known.add(serial)
            self._create_sensors_callback(self, serial)

        for listener in list(self._listeners):
            listener()
