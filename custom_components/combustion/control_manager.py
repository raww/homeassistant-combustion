"""Map HA control actions to UART commands over the shared connection."""
from __future__ import annotations

from custom_components.combustion.combustion_ble import uart
from custom_components.combustion.combustion_ble.uart import (
    CORE_SENSOR_INDEX,
    PowerMode,
    PredictionMode,
    set_probe_high_low_alarm,
)


class ControlManager:
    """Builds UART commands and sends them via the ConnectionManager."""

    def __init__(self, connection_manager) -> None:
        """Initialize."""
        self._conn = connection_manager
        self._target: dict[str, tuple[float, PredictionMode]] = {}
        self._alarms: dict[str, dict] = {}

    async def async_set_target(self, serial: str, temp_c: float, mode: PredictionMode) -> None:
        """Set the prediction target temperature and mode."""
        self._target[serial] = (temp_c, mode)
        await self._conn.async_send_command(serial, uart.set_prediction(temp_c, mode))

    async def async_set_mode(self, serial: str, mode: PredictionMode) -> None:
        """Change prediction mode, keeping the last-known target temperature.

        If no target has been set yet for this serial, it defaults to 0.0°C.
        """
        temp_c, _ = self._target.get(serial, (0.0, mode))
        await self.async_set_target(serial, temp_c, mode)

    async def async_silence(self, serial: str) -> None:
        """Silence active alarms."""
        await self._conn.async_send_command(serial, uart.silence_alarms())

    async def async_set_power_mode(self, serial: str, mode: PowerMode) -> None:
        """Set the probe power mode."""
        await self._conn.async_send_command(serial, uart.set_power_mode(mode))

    async def async_set_probe_id(self, serial: str, probe_id: int) -> None:
        """Set the probe ID (0-7)."""
        await self._conn.async_send_command(serial, uart.set_probe_id(probe_id))

    async def async_set_probe_colour(self, serial: str, colour: int) -> None:
        """Set the probe colour (0-7)."""
        await self._conn.async_send_command(serial, uart.set_probe_colour(colour))

    async def async_reset_probe(self, serial: str) -> None:
        """Reset the thermometer (wipes the cook session)."""
        await self._conn.async_send_command(serial, uart.reset_probe())

    async def async_reset_food_safe(self, serial: str) -> None:
        """Reset the Food Safe program state."""
        await self._conn.async_send_command(serial, uart.reset_food_safe())

    async def async_set_high_alarm(self, serial: str, temp_c: float) -> None:
        """Set the core sensor's high alarm threshold, keeping any remembered low alarm."""
        alarms = self._alarms.setdefault(serial, {"high": None, "low": None})
        alarms["high"] = temp_c
        await self._async_send_alarm_command(serial)

    async def async_set_low_alarm(self, serial: str, temp_c: float) -> None:
        """Set the core sensor's low alarm threshold, keeping any remembered high alarm."""
        alarms = self._alarms.setdefault(serial, {"high": None, "low": None})
        alarms["low"] = temp_c
        await self._async_send_alarm_command(serial)

    async def _async_send_alarm_command(self, serial: str) -> None:
        """Build and send the combined high/low alarm frame from remembered state.

        Only the core sensor is targeted; any alarm not yet set is sent as
        disabled (0x0000), matching the frame's fixed-width per-sensor layout.
        """
        alarms = self._alarms[serial]
        high, low = alarms["high"], alarms["low"]
        frame = set_probe_high_low_alarm(
            CORE_SENSOR_INDEX,
            high_enabled=(high is not None),
            high_temp_c=(high or 0.0),
            low_enabled=(low is not None),
            low_temp_c=(low or 0.0),
        )
        await self._conn.async_send_command(serial, frame)
