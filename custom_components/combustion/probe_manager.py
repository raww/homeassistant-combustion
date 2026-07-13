"""Manage discovered Combustion devices (probes and gauges)."""

import time

from homeassistant.core import callback

from custom_components.combustion.bluetooth_listener import BluetoothListener
from custom_components.combustion.combustion_ble.mode_id import ProbeMode
from custom_components.combustion.const import LOGGER

_LOGGER = LOGGER.getChild('probe_manager')

# Advertisements arrive roughly every 250ms (and from multiple bluetooth
# proxies); pushing every one of them through the entity state machine and
# recorder overwhelms Home Assistant. Updates are throttled per device.
# Configurable via the integration options.
DEFAULT_MIN_NOTIFY_INTERVAL_SECONDS = 1.0

# A device that has not advertised for this long is considered unavailable.
# Probes advertise every 250ms and gauges/nodes every few seconds, so silence
# means the device is off, out of range, or in its charger. Configurable via
# the integration options.
DEFAULT_AVAILABILITY_TIMEOUT_SECONDS = 90.0

# While direct probe advertisements are arriving, data repeated by MeatNet
# nodes (booster/display) for the same probe is ignored: the repeated copy can
# be slightly stale, and letting it overwrite fresh direct readings causes
# values to flip-flop. Repeated data is used again once the probe itself has
# been silent for this long (e.g. it is out of range of every proxy).
DIRECT_DATA_PREFERENCE_SECONDS = 5.0

# An instant read value older than this is no longer shown; the probe has
# left instant-read mode or gone silent.
INSTANT_READ_STALE_SECONDS = 15.0


class ProbeManager:
    """Manage discovered Combustion devices."""

    def __init__(
        self,
        bt_listener: BluetoothListener,
        availability_timeout_seconds: float = DEFAULT_AVAILABILITY_TIMEOUT_SECONDS,
        min_notify_interval_seconds: float = DEFAULT_MIN_NOTIFY_INTERVAL_SECONDS,
    ) -> None:
        """Initialize."""
        self.bluetooth_listener = bt_listener
        self.availability_timeout_seconds = availability_timeout_seconds
        self.min_notify_interval_seconds = min_notify_interval_seconds
        self.create_sensors_callback = None
        self.create_binary_sensors_callback = None
        self.data = {}
        self._listeners = []
        self._last_notify: dict[str, float] = {}
        self._last_seen: dict[str, float] = {}
        self._last_direct_seen: dict[str, float] = {}
        self._instant_read: dict[str, tuple[float, float]] = {}
        self._failed_devices: set[str] = set()

    def init_sensor_platform(self, create_sensors_callback):
        """Initialize sensor platform."""
        self.create_sensors_callback = create_sensors_callback

    def init_binary_sensor_platform(self, create_sensors_callback):
        """Initialize binary sensor platform."""
        self.create_binary_sensors_callback = create_sensors_callback

    def async_init(self):
        """Async initialization."""
        self.bluetooth_listener.add_update_listener(self.create_update_callback())

    def create_update_callback(self):
        """Create callback for handling updates."""
        @callback
        def update(device_data):
            """Handle updated data from a Combustion device."""
            serial = device_data.serial_number
            if serial in self._failed_devices:
                return

            now = time.monotonic()
            self._last_seen[serial] = now

            if device_data.device_type == 'PROBE':
                self._last_direct_seen[serial] = now
            elif device_data.device_type == 'MEAT_NET_NODE':
                last_direct = self._last_direct_seen.get(serial)
                if last_direct is not None and now - last_direct < DIRECT_DATA_PREFERENCE_SECONDS:
                    return

            # In instant-read mode the first thermistor carries the instant
            # read value and the remaining readings are not meaningful, so the
            # last normal-mode data is kept for the regular sensors.
            is_instant_read = getattr(device_data, 'mode', None) == ProbeMode.instantRead
            if is_instant_read:
                self._instant_read[serial] = (device_data.temperature_data[0], now)

            is_new = serial not in self.data
            if not is_instant_read or is_new:
                self.data[serial] = device_data

            if is_new:
                _LOGGER.debug("Adding sensors for new device [%s]", serial)
                try:
                    self.create_sensors_callback(self, device_data)
                    self.create_binary_sensors_callback(self, device_data)
                except Exception:  # noqa: BLE001
                    # Never retry a failing device on every advertisement; that
                    # creates an unbounded stream of duplicate entities and log spam.
                    self._failed_devices.add(serial)
                    _LOGGER.exception("Failed to create entities for device [%s]; ignoring this device", serial)
                    return

            if not is_new and now - self._last_notify.get(serial, 0.0) < self.min_notify_interval_seconds:
                return
            self._last_notify[serial] = now

            self.notify_listeners()

        return update

    def notify_listeners(self):
        """Notify all listeners that device state may have changed."""
        for listener in list(self._listeners):
            listener()

    def instant_read_temperature(self, serial_number: str):
        """Most recent instant read temperature, or None when stale/absent."""
        entry = self._instant_read.get(serial_number)
        if entry is None:
            return None
        value, seen_at = entry
        if time.monotonic() - seen_at > INSTANT_READ_STALE_SECONDS:
            return None
        return value

    def device_available(self, serial_number: str) -> bool:
        """Whether the device has advertised recently."""
        last_seen = self._last_seen.get(serial_number)
        if last_seen is None:
            return False
        return time.monotonic() - last_seen < self.availability_timeout_seconds

    def add_update_listener(self, listener):
        """Add listener to be notified of probe updates.

        Returns a callable that removes the listener again.
        """
        self._listeners.append(listener)

        def _remove_listener():
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove_listener

    def probe_data(self, serial_number: str):
        """Device data for provided serial number."""
        return self.data[serial_number]
