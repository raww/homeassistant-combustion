"""Custom integration to integrate combustion devices with Home Assistant.

For more details about this integration, please refer to
https://github.com/legrego/homeassistant-combustion
"""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from custom_components.combustion.bluetooth_listener import BluetoothListener
from custom_components.combustion.probe_manager import ProbeManager

from .const import DOMAIN

# How often entity availability is re-evaluated when no advertisements arrive.
AVAILABILITY_CHECK_INTERVAL = timedelta(seconds=30)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})

    listener = BluetoothListener(hass, entry)
    probe_manager = ProbeManager(listener)

    hass.data[DOMAIN] = probe_manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    probe_manager.async_init()
    listener.async_init()

    # When a device stops advertising, no bluetooth callback fires to push the
    # entities to unavailable; re-notify periodically so availability updates.
    entry.async_on_unload(
        async_track_time_interval(
            hass,
            lambda _now: probe_manager.notify_listeners(),
            AVAILABILITY_CHECK_INTERVAL,
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN] = {}
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
