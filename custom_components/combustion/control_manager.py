"""Map HA control actions to UART commands over the shared connection."""
from __future__ import annotations

from custom_components.combustion.combustion_ble import uart
from custom_components.combustion.combustion_ble.uart import PowerMode, PredictionMode


class ControlManager:
    """Builds UART commands and sends them via the ConnectionManager."""

    def __init__(self, connection_manager) -> None:
        """Initialize."""
        self._conn = connection_manager
        self._target: dict[str, tuple[float, PredictionMode]] = {}

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
