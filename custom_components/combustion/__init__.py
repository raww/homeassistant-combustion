"""Custom integration to integrate combustion devices with Home Assistant.

For more details about this integration, please refer to
https://github.com/legrego/homeassistant-combustion
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.loader import async_get_integration

from custom_components.combustion.bluetooth_listener import BluetoothListener
from custom_components.combustion.connection_manager import ConnectionManager
from custom_components.combustion.prediction_manager import PredictionManager
from custom_components.combustion.probe_manager import ProbeManager

from .const import (
    CONF_AVAILABILITY_TIMEOUT,
    CONF_ENABLE_ACTIVE_CONNECTION,
    CONF_UPDATE_THROTTLE,
    DEFAULT_AVAILABILITY_TIMEOUT,
    DEFAULT_ENABLE_ACTIVE_CONNECTION,
    DEFAULT_UPDATE_THROTTLE,
    DOMAIN,
    LOGGER,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR
]

FRONTEND_CARD_URL = "/combustion/combustion-card.js"
FRONTEND_REGISTERED_KEY = f"{DOMAIN}_frontend_registered"


async def _async_register_frontend_card(hass: HomeAssistant) -> None:
    """Serve and auto-load the bundled combustion-card Lovelace card.

    Best-effort: dashboards work without it, so a failure (e.g. frontend not
    loaded, as in tests) must never break integration setup.
    """
    if hass.data.get(FRONTEND_REGISTERED_KEY):
        return
    try:
        http = getattr(hass, 'http', None)
        if http is None:
            return
        card_path = str(Path(__file__).parent / "www" / "combustion-card.js")
        try:
            from homeassistant.components.http import StaticPathConfig
            await http.async_register_static_paths(
                [StaticPathConfig(FRONTEND_CARD_URL, card_path, True)]
            )
        except ImportError:
            # Home Assistant < 2024.6
            http.register_static_path(FRONTEND_CARD_URL, card_path, True)

        from homeassistant.components.frontend import add_extra_js_url
        integration = await async_get_integration(hass, DOMAIN)
        version = integration.version or "0"
        add_extra_js_url(hass, f"{FRONTEND_CARD_URL}?v={version}")
        hass.data[FRONTEND_REGISTERED_KEY] = True
    except Exception:  # noqa: BLE001
        LOGGER.debug("Could not register the combustion card frontend resource", exc_info=True)


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})

    await _async_register_frontend_card(hass)

    availability_timeout = entry.options.get(CONF_AVAILABILITY_TIMEOUT, DEFAULT_AVAILABILITY_TIMEOUT)
    update_throttle = entry.options.get(CONF_UPDATE_THROTTLE, DEFAULT_UPDATE_THROTTLE)
    enable_active_connection = entry.options.get(CONF_ENABLE_ACTIVE_CONNECTION, DEFAULT_ENABLE_ACTIVE_CONNECTION)

    listener = BluetoothListener(hass, entry)
    probe_manager = ProbeManager(
        listener,
        availability_timeout_seconds=float(availability_timeout),
        min_notify_interval_seconds=float(update_throttle),
    )

    hass.data[DOMAIN] = probe_manager

    connection_manager = ConnectionManager(hass, entry, probe_manager, bool(enable_active_connection))
    prediction_manager = PredictionManager(hass, entry, connection_manager, probe_manager)
    hass.data[f"{DOMAIN}_prediction"] = prediction_manager
    hass.data[f"{DOMAIN}_connection"] = connection_manager

    # The entity platforms reach the managers through hass.data[DOMAIN] (the
    # ProbeManager). Attach them here as the single hand-off seam; the control
    # manager and active-connection flag are populated by later tasks.
    probe_manager.connection_manager = connection_manager
    probe_manager.control_manager = None
    probe_manager.active_enabled = bool(enable_active_connection)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    probe_manager.async_init()
    listener.async_init()
    prediction_manager.async_init()
    connection_manager.async_init()

    # When a device stops advertising, no bluetooth callback fires to push the
    # entities to unavailable; re-notify periodically so availability updates.
    # The @callback decoration is essential: without it Home Assistant runs
    # the job in a thread-pool executor, and the resulting state writes from
    # outside the event loop are rejected (and unsafe).
    @callback
    def _async_availability_tick(_now) -> None:
        probe_manager.notify_listeners()

    availability_check_interval = timedelta(seconds=max(5.0, float(availability_timeout) / 3))
    entry.async_on_unload(
        async_track_time_interval(
            hass,
            _async_availability_tick,
            availability_check_interval,
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN] = {}
        hass.data.pop(f"{DOMAIN}_prediction", None)
        hass.data.pop(f"{DOMAIN}_connection", None)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry.

    Must go through hass.config_entries so the entry's async_on_unload
    callbacks run (bluetooth callback, availability timer, update listener).
    Calling async_unload_entry/async_setup_entry directly skips them, leaking
    one extra bluetooth callback, timer and update listener per reload — the
    update listeners then multiply on every entry update until advertisement
    processing swamps the event loop.
    """
    await hass.config_entries.async_reload(entry.entry_id)
