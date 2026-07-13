"""Listen for all Bluetooth advertisements from the Combustion, Inc. manufacturer."""
from home_assistant_bluetooth import BluetoothServiceInfoBleak
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.combustion.combustion_ble.advertising_data import (
    CombustionProductType,
)
from custom_components.combustion.combustion_ble.combustion_probe_data import (
    CombustionProbeData,
)
from custom_components.combustion.combustion_ble.gauge_data import CombustionGaugeData
from custom_components.combustion.const import BT_MANUFACTURER_ID, LOGGER

_LOGGER = LOGGER.getChild('bluetooth-listener')

# Product types whose advertisements carry probe data.
_PROBE_DATA_TYPES = (CombustionProductType.PROBE, CombustionProductType.MEAT_NET_NODE)


class BluetoothListener:
    """Listen for all Bluetooth advertisements from the Combustion, Inc. manufacturer."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize."""
        self.hass = hass
        self.config_entry = config_entry
        self._listeners = []
        self._parse_failures = set()

    def add_update_listener(self, listener):
        """Add a listener to be notified of new BT data."""
        self._listeners.append(listener)

    def async_init(self):
        """Async initialization."""
        self.config_entry.async_on_unload(
            bluetooth.async_register_callback(
                self.hass,
                self._bt_callback,
                bluetooth.BluetoothCallbackMatcher(manufacturer_id=BT_MANUFACTURER_ID, connectable=False),
                bluetooth.BluetoothScanningMode.ACTIVE
            )
        )
        self.config_entry.async_on_unload(self.async_unload)

    def async_unload(self):
        """Async unload."""
        self._listeners.clear()

    def _bt_callback(self, service_info: BluetoothServiceInfoBleak, change):
        """Handle incoming BT advertisements."""
        if self.hass.is_stopping:
            return

        try:
            device_data = self._parse_advertisement(service_info)
        except Exception:  # noqa: BLE001 - a parse failure must never propagate into the bluetooth manager
            if service_info.address not in self._parse_failures:
                self._parse_failures.add(service_info.address)
                _LOGGER.warning(
                    "Failed to parse advertisement from [%s]; further failures from this device will not be logged",
                    service_info.address,
                    exc_info=True,
                )
            return

        if device_data is None:
            return

        for listener in self._listeners:
            listener(device_data)

    def _parse_advertisement(self, service_info: BluetoothServiceInfoBleak):
        """Parse a manufacturer advertisement into device data, or None to discard."""
        payload = service_info.manufacturer_data.get(BT_MANUFACTURER_ID)
        if not payload:
            return None

        product_type = CombustionProductType.from_byte(payload[0])

        if product_type in _PROBE_DATA_TYPES:
            probe_data = CombustionProbeData.from_advertisement(service_info)
            if probe_data is None or not probe_data.valid:
                _LOGGER.debug("Discarding invalid advertisement from [%s]", service_info.address)
                return None
            return probe_data

        if product_type == CombustionProductType.GAUGE:
            gauge_data = CombustionGaugeData.from_advertisement(service_info)
            if gauge_data is None or not gauge_data.valid:
                _LOGGER.debug("Discarding invalid gauge advertisement from [%s]", service_info.address)
                return None
            return gauge_data

        # Displays, boosters, engines and unknown future products don't carry
        # sensor data in their advertisements.
        _LOGGER.debug("Ignoring %s advertisement from [%s]", product_type.name, service_info.address)
        return None
