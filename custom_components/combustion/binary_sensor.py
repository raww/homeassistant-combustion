"""Binary sensor platform for combustion."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityPlatformState
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.combustion.probe_manager import ProbeManager

from .const import DOMAIN, LOGGER
from .entity import CombustionEntity

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


def _create_binary_sensors(probe_manager: ProbeManager, device_data):
    if device_data.device_type == 'GAUGE':
        return [
            CombustionBatterySensor(probe_manager, device_data, device_name=GAUGE_DEVICE_NAME),
            CombustionGaugeSensorPresentSensor(probe_manager, device_data),
            CombustionGaugeOverheatingSensor(probe_manager, device_data),
            CombustionGaugeAlarmSensor(probe_manager, device_data, 'high'),
            CombustionGaugeAlarmSensor(probe_manager, device_data, 'low'),
        ]

    return [
        CombustionBatterySensor(probe_manager, device_data),
        CombustionProbeOverheatingSensor(probe_manager, device_data),
        CombustionProbeInsertedSensor(probe_manager, device_data),
        CombustionCookingSensor(probe_manager, device_data),
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


COOKING_DESCRIPTION = BinarySensorEntityDescription(
    key="probe_cooking",
    name="Cooking",
    device_class=BinarySensorDeviceClass.RUNNING
)

INSERTED_DESCRIPTION = BinarySensorEntityDescription(
    key="probe_inserted",
    name="Probe inserted",
)

# Insertion is detected from the tip-to-handle temperature differential: a
# probe lying on a surface reads near-uniform across all sensors, while a
# probe in food (fridge-cold meat on the counter, meat in a cooker, or hot
# meat resting) shows a large core/ambient spread. Hysteresis avoids
# flapping. A probe inserted into room-temperature food shows no differential
# until the cook starts; that is a physical limit of advertisement data.
INSERTED_ON_DIFF_C = 8.0
INSERTED_OFF_DIFF_C = 4.0

# Cooking additionally requires ambient heat no indoor environment reaches.
# Below this (e.g. cold smoking) use the "Probe inserted" sensor instead.
COOKING_ON_AMBIENT_C = 45.0
COOKING_OFF_AMBIENT_C = 40.0


class _ProbeTemperatureHeuristicSensor(BaseCombustionBinarySensor):
    """Shared plumbing for insertion/cooking heuristics."""

    def _readings(self):
        """Return (core, ambient) or None."""
        data = self._device_data()
        if data is None:
            return None
        try:
            (_c, core) = data.core_sensor
            (_a, ambient) = data.ambient_sensor
        except Exception:
            return None
        return (core, ambient)

    def _inserted(self, previous: bool) -> bool | None:
        readings = self._readings()
        if readings is None:
            return None
        (core, ambient) = readings
        threshold = INSERTED_OFF_DIFF_C if previous else INSERTED_ON_DIFF_C
        return abs(ambient - core) >= threshold

    @property
    def extra_state_attributes(self):
        """Current core/ambient readings backing the state."""
        readings = self._readings()
        if readings is None:
            return None
        (core, ambient) = readings
        return {
            'core_temperature': round(core, 1),
            'ambient_temperature': round(ambient, 1),
            'differential': round(abs(ambient - core), 1),
        }


class CombustionProbeInsertedSensor(_ProbeTemperatureHeuristicSensor):
    """Whether the probe appears to be inserted in food.

    On when the core/ambient differential reaches 8C (e.g. fridge-cold meat
    at room temperature, or any active cook or rest); off below 4C.
    """

    def __init__(self, probe_manager: ProbeManager, device_data) -> None:
        """Initialize."""
        super().__init__(probe_manager, device_data)
        self._attr_unique_id = f'{device_data.serial_number}--inserted'
        self.entity_description = INSERTED_DESCRIPTION
        self._state = False

    @property
    def name(self):
        """Sensor name."""
        return 'Probe inserted'

    @property
    def is_on(self) -> bool | None:
        """Return true while the probe appears to be inserted."""
        inserted = self._inserted(self._state)
        if inserted is None:
            return None
        self._state = inserted
        return inserted


class CombustionCookingSensor(_ProbeTemperatureHeuristicSensor):
    """Whether the probe appears to be in an active cook.

    On when the probe is inserted AND the ambient sensor reaches 45C; off
    below 40C or when no longer inserted. Resting meat therefore reads as
    inserted but not cooking.
    """

    def __init__(self, probe_manager: ProbeManager, device_data) -> None:
        """Initialize."""
        super().__init__(probe_manager, device_data)
        self._attr_unique_id = f'{device_data.serial_number}--cooking'
        self.entity_description = COOKING_DESCRIPTION
        self._cooking = False

    @property
    def name(self):
        """Sensor name."""
        return 'Cooking'

    @property
    def is_on(self) -> bool | None:
        """Return true while the probe appears to be cooking."""
        readings = self._readings()
        if readings is None:
            return None
        (_core, ambient) = readings

        inserted = self._inserted(self._cooking)
        ambient_threshold = COOKING_OFF_AMBIENT_C if self._cooking else COOKING_ON_AMBIENT_C
        self._cooking = bool(inserted) and ambient >= ambient_threshold
        return self._cooking


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
