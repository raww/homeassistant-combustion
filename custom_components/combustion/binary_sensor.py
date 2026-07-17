"""Binary sensor platform for combustion."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityPlatformState
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.combustion.probe_manager import ProbeManager

from .const import DOMAIN, LOGGER
from .entity import CombustionConnectionGatedEntity, CombustionEntity

_LOGGER = LOGGER.getChild('binary_sensor')

GAUGE_DEVICE_NAME = 'Grill Gauge'

BATTERY_DESCRIPTION = BinarySensorEntityDescription(
    key="probe_battery_ok",
    name="Battery",
    device_class=BinarySensorDeviceClass.BATTERY
)

GAUGE_SENSOR_PRESENT_DESCRIPTION = BinarySensorEntityDescription(
    key="gauge_sensor_present",
    name="Sensor connected",
    device_class=BinarySensorDeviceClass.CONNECTIVITY
)

GAUGE_OVERHEATING_DESCRIPTION = BinarySensorEntityDescription(
    key="gauge_overheating",
    name="Overheating",
    device_class=BinarySensorDeviceClass.PROBLEM
)

GAUGE_HIGH_ALARM_DESCRIPTION = BinarySensorEntityDescription(
    key="gauge_high_alarm",
    name="High alarm",
)

GAUGE_LOW_ALARM_DESCRIPTION = BinarySensorEntityDescription(
    key="gauge_low_alarm",
    name="Low alarm",
)


NODE_DEVICE_NAMES = {'BOOSTER': 'Booster', 'DISPLAY': 'Display'}

HIGH_RADIO_POWER_DESCRIPTION = BinarySensorEntityDescription(
    key="high_radio_power",
    name="High radio power",
    entity_category=EntityCategory.DIAGNOSTIC,
)


def _create_binary_sensors(probe_manager: ProbeManager, device_data):
    if device_data.device_type == 'GAUGE':
        return [
            CombustionBatterySensor(probe_manager, device_data, device_name=GAUGE_DEVICE_NAME),
            CombustionGaugeSensorPresentSensor(probe_manager, device_data),
            CombustionGaugeOverheatingSensor(probe_manager, device_data),
            CombustionGaugeAlarmSensor(probe_manager, device_data, 'high'),
            CombustionGaugeAlarmSensor(probe_manager, device_data, 'low'),
        ]

    if device_data.device_type in ('BOOSTER', 'DISPLAY'):
        return [CombustionHighRadioPowerSensor(probe_manager, device_data)]

    return [
        CombustionBatterySensor(probe_manager, device_data),
        CombustionProbeOverheatingSensor(probe_manager, device_data),
    ]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the binary_sensor platform."""
    _LOGGER.debug("Starting async_setup_entry")

    def _create_sensors_callback(pm: ProbeManager, device_data):
        sensors = _create_binary_sensors(pm, device_data)
        async_add_entities(sensors)

    probe_manager: ProbeManager = hass.data[DOMAIN]
    probe_manager.init_binary_sensor_platform(_create_sensors_callback)


class BaseCombustionBinarySensor(CombustionEntity, BinarySensorEntity):
    """Base class for combustion binary sensors."""

    def __init__(self, probe_manager: ProbeManager, device_data, device_name=None) -> None:
        """Initialize."""
        if device_name is None:
            super().__init__(device_data.serial_number)
        else:
            super().__init__(device_data.serial_number, device_name=device_name)
        self.device_serial_number = device_data.serial_number
        self.probe_manager = probe_manager
        self._attr_has_entity_name = True

    @callback
    def on_update(self):
        """Process device updates."""
        if self._platform_state == EntityPlatformState.ADDED:
            self.async_schedule_update_ha_state()

    def _device_data(self):
        """Return current data for this device, or None if unavailable."""
        try:
            return self.probe_manager.probe_data(self.device_serial_number)
        except KeyError:
            return None


class CombustionBatterySensor(BaseCombustionBinarySensor):
    """Low battery binary sensor."""

    def __init__(self, probe_manager: ProbeManager, device_data, device_name=None) -> None:
        """Initialize."""
        super().__init__(probe_manager, device_data, device_name=device_name)
        self._attr_unique_id = f'{device_data.serial_number}--battery'
        self.entity_description = BATTERY_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Battery'

    @property
    def is_on(self) -> bool | None:
        """Return true if the battery is low."""
        data = self._device_data()
        return None if data is None else not data.battery_ok


class CombustionProbeOverheatingSensor(BaseCombustionBinarySensor):
    """Whether any of the probe's thermistors is overheating."""

    def __init__(self, probe_manager: ProbeManager, device_data) -> None:
        """Initialize."""
        super().__init__(probe_manager, device_data)
        self._attr_unique_id = f'{device_data.serial_number}--overheating'
        self.entity_description = GAUGE_OVERHEATING_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Overheating'

    @property
    def is_on(self) -> bool | None:
        """Return true if any thermistor is overheating."""
        data = self._device_data()
        return None if data is None else data.overheating

    @property
    def extra_state_attributes(self):
        """List of overheating thermistors."""
        data = self._device_data()
        if data is None:
            return None
        return {'overheating_sensors': data.overheating_sensor_numbers}


class CombustionGaugeSensorPresentSensor(BaseCombustionBinarySensor):
    """Whether the gauge's temperature sensor is attached."""

    def __init__(self, probe_manager: ProbeManager, device_data) -> None:
        """Initialize."""
        super().__init__(probe_manager, device_data, device_name=GAUGE_DEVICE_NAME)
        self._attr_unique_id = f'{device_data.serial_number}--sensor-present'
        self.entity_description = GAUGE_SENSOR_PRESENT_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Sensor connected'

    @property
    def is_on(self) -> bool | None:
        """Return true if the temperature sensor is attached."""
        data = self._device_data()
        return None if data is None else data.sensor_present


class CombustionGaugeOverheatingSensor(BaseCombustionBinarySensor):
    """Whether the gauge's temperature sensor is overheating."""

    def __init__(self, probe_manager: ProbeManager, device_data) -> None:
        """Initialize."""
        super().__init__(probe_manager, device_data, device_name=GAUGE_DEVICE_NAME)
        self._attr_unique_id = f'{device_data.serial_number}--overheating'
        self.entity_description = GAUGE_OVERHEATING_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Overheating'

    @property
    def is_on(self) -> bool | None:
        """Return true if the sensor is overheating."""
        data = self._device_data()
        return None if data is None else data.sensor_overheating


class CombustionGaugeAlarmSensor(BaseCombustionBinarySensor):
    """High or low alarm state of the gauge."""

    def __init__(self, probe_manager: ProbeManager, device_data, alarm_kind: str) -> None:
        """Initialize."""
        super().__init__(probe_manager, device_data, device_name=GAUGE_DEVICE_NAME)
        self._alarm_kind = alarm_kind
        self._attr_unique_id = f'{device_data.serial_number}--{alarm_kind}-alarm'
        self.entity_description = GAUGE_HIGH_ALARM_DESCRIPTION if alarm_kind == 'high' else GAUGE_LOW_ALARM_DESCRIPTION

    def _alarm(self):
        data = self._device_data()
        if data is None:
            return None
        return data.high_alarm if self._alarm_kind == 'high' else data.low_alarm

    @property
    def name(self):
        """Sensor name."""
        return f'{self._alarm_kind.capitalize()} alarm'

    @property
    def is_on(self) -> bool | None:
        """Return true if the alarm is currently alarming."""
        alarm = self._alarm()
        return None if alarm is None else alarm.alarming

    @property
    def extra_state_attributes(self):
        """Alarm configuration details."""
        alarm = self._alarm()
        if alarm is None:
            return None
        return {
            'set': alarm.is_set,
            'tripped': alarm.tripped,
            'alarm_temperature': round(alarm.temperature, 1) if alarm.is_set else None,
        }


class CombustionHighRadioPowerSensor(BaseCombustionBinarySensor):
    """Whether a MeatNet repeater transmits at high radio power (+8 dBm)."""

    def __init__(self, probe_manager: ProbeManager, device_data) -> None:
        """Initialize."""
        super().__init__(probe_manager, device_data,
                         device_name=NODE_DEVICE_NAMES.get(device_data.device_type, 'Booster'))
        self._attr_unique_id = f'{device_data.serial_number}--high-radio-power'
        self.entity_description = HIGH_RADIO_POWER_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'High radio power'

    @property
    def is_on(self) -> bool | None:
        """Return true if the repeater is in high radio power mode."""
        data = self._device_data()
        return None if data is None else data.high_radio_power


class CombustionConnectedSensor(CombustionConnectionGatedEntity, BinarySensorEntity):
    """Diagnostic sensor reporting the probe's BLE connection state.

    Unlike the number/select/button control entities that share
    `CombustionConnectionGatedEntity`, this sensor's entire purpose is to
    report whether the device is connected, so it must stay available even
    while disconnected -- otherwise it could never show "disconnected".
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, connection_manager, device_data) -> None:
        """Initialize."""
        super().__init__(connection_manager, device_data)
        self._attr_unique_id = f'{device_data.serial_number}--connected'

    @property
    def available(self) -> bool:
        """Always available, so it can report the disconnected state too."""
        return True

    @property
    def name(self):
        """Sensor name."""
        return 'Connected'

    @property
    def is_on(self) -> bool:
        """Return true if currently connected over BLE."""
        return self._conn.is_connected(self._serial)
