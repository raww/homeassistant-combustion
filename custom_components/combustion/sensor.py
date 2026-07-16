"""Sensor platform for combustion."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityPlatformState
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from sensor_state_data import Units

from custom_components.combustion.combustion_ble.combustion_probe_data import (
    CombustionProbeData,
)
from custom_components.combustion.entity import CombustionEntity
from custom_components.combustion.probe_manager import ProbeManager

from .const import DEVICE_NAME, DOMAIN, LOGGER

_LOGGER = LOGGER.getChild('sensor')

# Device names shown on the HA device page, keyed by advertisement device type.
DEVICE_NAMES = {'GAUGE': 'Grill Gauge', 'BOOSTER': 'Booster', 'DISPLAY': 'Display'}

VIRTUAL_TEMPERATURE_SENSOR_DESCRIPTION = SensorEntityDescription(
    key=f"{SensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1
)

TEMPERATURE_SENSOR_DESCRIPTION = SensorEntityDescription(
    key=f"{SensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
    entity_registry_enabled_default=False,
)

RSSI_SENSOR_DESCRIPTION = SensorEntityDescription(
    key=f"{SensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
)

SENSOR_DESCRIPTIONS = {
    (
        SensorDeviceClass.TEMPERATURE,
        Units.TEMP_CELSIUS,
    ): SensorEntityDescription(
        key=f"{SensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        SensorDeviceClass.ENUM.value,
        None
    ): SensorEntityDescription(
        key=f"{SensorDeviceClass.ENUM}_mode",
        device_class=SensorDeviceClass.ENUM,
        options=['normal', 'instant_read', 'error', 'reserved', 'unknown']
    ),
    (
        SensorDeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{SensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
}

def _create_temperature_sensors(probe_manager: ProbeManager, probe_data: CombustionProbeData):
    sensors: list[BaseCombustionTemperatureSensor] = [
        CombustionVirtualCoreSensor(probe_manager, probe_data),
        CombustionVirtualSurfaceSensor(probe_manager, probe_data),
        CombustionVirtualAmbientSensor(probe_manager, probe_data),
        CombustionInstantReadSensor(probe_manager, probe_data),
    ]
    for i in range(len(probe_data.temperature_data)):
        sensors.append(CombustionTemperatureSensor(probe_manager, probe_data, i + 1))

    return sensors

def _create_diagnostic_sensors(probe_manager: ProbeManager, probe_data: CombustionProbeData):
    sensors: list[CombustionEntity] = [
        CombustionRSSISensor(probe_manager, probe_data),
        CombustionModeSensor(probe_manager, probe_data),
    ]

    return sensors

def _create_gauge_sensors(probe_manager: ProbeManager, gauge_data):
    sensors: list[CombustionEntity] = [
        CombustionGaugeTemperatureSensor(probe_manager, gauge_data),
        CombustionGaugeZoneSensor(probe_manager, gauge_data),
        CombustionRSSISensor(probe_manager, gauge_data),
    ]

    return sensors

def _create_prediction_sensors(prediction_manager, serial: str):
    sensors: list[CombustionEntity] = [
        CombustionPredictionStateSensor(prediction_manager, serial),
        CombustionReadyInSensor(prediction_manager, serial),
        CombustionSetpointSensor(prediction_manager, serial),
        CombustionEstimatedCoreSensor(prediction_manager, serial),
    ]
    return sensors


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the sensor platform."""
    _LOGGER.debug("Starting async_setup_entry")

    def _create_sensors_callback(pm: ProbeManager, device_data):
        if device_data.device_type == 'GAUGE':
            sensors = _create_gauge_sensors(pm, device_data)
        elif device_data.device_type in ('BOOSTER', 'DISPLAY'):
            sensors = [CombustionRSSISensor(pm, device_data)]
        else:
            sensors = _create_temperature_sensors(pm, device_data)
            sensors.extend(_create_diagnostic_sensors(pm, device_data))
        async_add_entities(sensors)

    probe_manager: ProbeManager = hass.data[DOMAIN]
    probe_manager.init_sensor_platform(_create_sensors_callback)

    prediction_manager = hass.data.get(f"{DOMAIN}_prediction")
    if prediction_manager is not None:
        def _create_prediction_callback(prm, serial):
            async_add_entities(_create_prediction_sensors(prm, serial))
        prediction_manager.init_sensor_platform(_create_prediction_callback)

class CombustionGaugeTemperatureSensor(CombustionEntity, SensorEntity):
    """Temperature sensor for a Combustion Gauge."""

    def __init__(self, probe_manager: ProbeManager, gauge_data) -> None:
        """Initialize."""
        super().__init__(gauge_data.serial_number, device_name='Grill Gauge')
        self.device_serial_number = gauge_data.serial_number
        self.probe_manager = probe_manager
        self._attr_has_entity_name = True
        self._attr_unique_id = f'{gauge_data.serial_number}--gauge-temperature'
        self.entity_description = VIRTUAL_TEMPERATURE_SENSOR_DESCRIPTION

    @property
    def should_poll(self) -> bool:
        """Do not poll for updates."""
        return False

    @property
    def name(self):
        """Sensor name."""
        return 'Temperature'

    @callback
    def on_update(self):
        """Process gauge updates."""
        if self._platform_state == EntityPlatformState.ADDED:
            self.async_schedule_update_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return the gauge temperature, or None while no sensor is attached."""
        try:
            return self.probe_manager.probe_data(self.device_serial_number).temperature
        except Exception as ex:
            _LOGGER.debug("Error getting gauge temperature for native_value: %s", ex)
            return None

GAUGE_ZONE_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="gauge_zone",
    device_class=SensorDeviceClass.ENUM,
    options=['off', 'smoke', 'bbq', 'low_grill', 'med', 'high', 'insane'],
)


class CombustionGaugeZoneSensor(CombustionEntity, SensorEntity):
    """Cooking zone of a Combustion Gauge (SMOKE..INSANE)."""

    def __init__(self, probe_manager: ProbeManager, gauge_data) -> None:
        """Initialize."""
        super().__init__(gauge_data.serial_number, device_name='Grill Gauge')
        self.device_serial_number = gauge_data.serial_number
        self.probe_manager = probe_manager
        self._attr_has_entity_name = True
        self._attr_unique_id = f'{gauge_data.serial_number}--gauge-zone'
        self.entity_description = GAUGE_ZONE_SENSOR_DESCRIPTION

    @property
    def should_poll(self) -> bool:
        """Do not poll for updates."""
        return False

    @property
    def name(self):
        """Sensor name."""
        return 'Zone'

    @callback
    def on_update(self):
        """Process gauge updates."""
        if self._platform_state == EntityPlatformState.ADDED:
            self.async_schedule_update_ha_state()

    @property
    def native_value(self) -> str | None:
        """Return the current cooking zone."""
        try:
            return self.probe_manager.probe_data(self.device_serial_number).grill_zone
        except Exception as ex:
            _LOGGER.debug("Error getting gauge zone for native_value: %s", ex)
            return None


MODE_SENSOR_ENTITY_DESCRIPTION = SensorEntityDescription(
    key="probe_mode",
    device_class=SensorDeviceClass.ENUM,
    options=['normal', 'instant_read', 'error', 'reserved', 'unknown'],
    entity_category=EntityCategory.DIAGNOSTIC,
)


class CombustionModeSensor(CombustionEntity, SensorEntity):
    """Probe mode diagnostic sensor (normal / instant read / error)."""

    def __init__(self, probe_manager: ProbeManager, probe_data: CombustionProbeData) -> None:
        """Initialize."""
        super().__init__(probe_data.serial_number)
        self.device_serial_number = probe_data.serial_number
        self.probe_manager = probe_manager
        self._attr_has_entity_name = True
        self._attr_unique_id = f'{probe_data.serial_number}--mode'
        self.entity_description = MODE_SENSOR_ENTITY_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Mode'

    @callback
    def on_update(self):
        """Process probe updates."""
        if self._platform_state == EntityPlatformState.ADDED:
            self.async_schedule_update_ha_state()

    @property
    def native_value(self) -> str | None:
        """Return the probe mode."""
        try:
            return self.probe_manager.probe_data(self.device_serial_number).mode_name
        except Exception as ex:
            _LOGGER.debug("Error getting mode for native_value: %s", ex)
            return None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Probe identity and data-source attributes."""
        try:
            data = self.probe_manager.probe_data(self.device_serial_number)
            return {
                'probe_id': data.probe_id,
                'color': data.color_name,
                'source_address': data.address,
                'via_repeater': data.via_repeater,
                'hops': data.hops,
            }
        except Exception:
            return None


class CombustionRSSISensor(CombustionEntity, SensorEntity):
    """RSSI diagnostic sensor."""

    def __init__(self, probe_manager: ProbeManager, probe_data) -> None:
        """Initialize."""
        super().__init__(probe_data.serial_number, device_name=DEVICE_NAMES.get(probe_data.device_type, DEVICE_NAME))
        self.device_serial_number = probe_data.serial_number
        self.probe_manager = probe_manager
        self._attr_has_entity_name = True
        self._attr_unique_id = f'{probe_data.serial_number}--rssi'
        self.entity_description = RSSI_SENSOR_DESCRIPTION
        # A repeater's only real self-data is its signal, so surface it.
        if probe_data.device_type in ('BOOSTER', 'DISPLAY'):
            self._attr_entity_registry_enabled_default = True

    @property
    def should_poll(self) -> bool:
        """Do not poll for updates."""
        return False

    @property
    def name(self):
        """Sensor name."""
        return 'RSSI'

    @callback
    def on_update(self):
        """Process probe updates."""
        _LOGGER.debug("Sensor [%s] with state [%s] has been notified of an update", self.unique_id, self._platform_state)
        if self._platform_state == EntityPlatformState.ADDED:
            self.async_schedule_update_ha_state()

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        try:
            return self.probe_manager.probe_data(self.device_serial_number).rssi
        except Exception as ex:
            _LOGGER.debug("Error getting rssi for native_value: %s", ex)
            return None

class BaseCombustionTemperatureSensor(CombustionEntity, SensorEntity):
    """Base class for temperature sensors."""

    def __init__(self, probe_manager: ProbeManager, probe_data: CombustionProbeData) -> None:
        """Initialize."""
        super().__init__(probe_data.serial_number)
        self.device_serial_number = probe_data.serial_number
        self.probe_manager = probe_manager
        self._attr_has_entity_name = True

    @callback
    def on_update(self):
        """Process probe updates."""
        _LOGGER.debug("Sensor [%s] has been notified of an update", self.unique_id)
        if self._platform_state == EntityPlatformState.ADDED:
            self.async_schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Do not poll for updates."""
        return False

class CombustionTemperatureSensor(BaseCombustionTemperatureSensor):
    """Combustion Temperature Sensor class."""

    def __init__(self, probe_manager: ProbeManager, probe_data: CombustionProbeData, thermistor_id: int) -> None:
        """Initialize."""
        super().__init__(probe_manager, probe_data)
        self.thermistor_id = thermistor_id
        self._attr_unique_id = f'{probe_data.serial_number}--thermistor--{thermistor_id}'
        self.entity_description = TEMPERATURE_SENSOR_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return f'Temperature {self.thermistor_id}'

    @property
    def native_value(self) -> float | None:
        """Return the native value of the sensor."""
        try:
            return self.probe_manager.probe_data(self.device_serial_number).temperature_data[self.thermistor_id - 1]
        except Exception as ex:
            _LOGGER.debug("Error getting thermistor temp for native_value: %s", ex)
            return None

class CombustionInstantReadSensor(BaseCombustionTemperatureSensor):
    """Instant read temperature sensor.

    Only reports a value while the probe is in instant-read mode; values go
    stale (None) shortly after the probe returns to normal mode.
    """

    def __init__(self, probe_manager: ProbeManager, probe_data: CombustionProbeData) -> None:
        """Initialize."""
        super().__init__(probe_manager, probe_data)
        self._attr_unique_id = f'{probe_data.serial_number}--sensor--instant-read'
        self.entity_description = VIRTUAL_TEMPERATURE_SENSOR_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Instant Read Temperature'

    @property
    def native_value(self) -> float | None:
        """Return the instant read temperature, or None when not instant reading."""
        return self.probe_manager.instant_read_temperature(self.device_serial_number)


class CombustionVirtualCoreSensor(BaseCombustionTemperatureSensor):
    """Combustion virtual core sensor class."""

    def __init__(self, probe_manager: ProbeManager, probe_data: CombustionProbeData) -> None:
        """Initialize."""
        super().__init__(probe_manager, probe_data)
        self._attr_unique_id = f'{probe_data.serial_number}--sensor--core'
        self.entity_description = VIRTUAL_TEMPERATURE_SENSOR_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Core Temperature'

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        try:
            (_thermistor_id, temp) = self.probe_manager.probe_data(self.device_serial_number).core_sensor
        except Exception as ex:
            _LOGGER.debug("Error getting core_sensor temp for native_value: %s", ex)
            return None
        return temp

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """State attributes."""
        try:
            (thermistor_id, _temp) = self.probe_manager.probe_data(self.device_serial_number).core_sensor
        except Exception as ex:
            _LOGGER.warning("Error getting core_sensor id for extra_state_attributes: %s", ex)
            return {}

        return {
            "thermistor_id": thermistor_id
        }

class CombustionVirtualAmbientSensor(BaseCombustionTemperatureSensor):
    """Combustion virtual ambient sensor class."""

    def __init__(self, probe_manager: ProbeManager, probe_data: CombustionProbeData) -> None:
        """Initialize."""
        super().__init__(probe_manager, probe_data)
        self._attr_unique_id = f'{probe_data.serial_number}--sensor--ambient'
        self.entity_description = VIRTUAL_TEMPERATURE_SENSOR_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Ambient Temperature'

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        try:
            (_thermistor_id, temp) = self.probe_manager.probe_data(self.device_serial_number).ambient_sensor
        except Exception as ex:
            _LOGGER.debug("Error getting ambient_sensor temp for native_value: %s", ex)
            return None

        return temp

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """State attributes."""
        try:
            (thermistor_id, _temp) = self.probe_manager.probe_data(self.device_serial_number).ambient_sensor
        except Exception as ex:
            _LOGGER.warning("Error getting ambient_sensor id for extra_state_attributes: %s", ex)
            return {}

        return {
            "thermistor_id": thermistor_id
        }

class CombustionVirtualSurfaceSensor(BaseCombustionTemperatureSensor):
    """Combustion virtual surface sensor class."""

    def __init__(self, probe_manager: ProbeManager, probe_data: CombustionProbeData) -> None:
        """Initialize."""
        super().__init__(probe_manager, probe_data)
        self._attr_unique_id = f'{probe_data.serial_number}--sensor--surface'
        self.entity_description = VIRTUAL_TEMPERATURE_SENSOR_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Surface Temperature'

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        try:
            (_thermistor_id, temp) = self.probe_manager.probe_data(self.device_serial_number).surface_sensor
        except Exception as ex:
            _LOGGER.debug("Error getting surface_sensor temp for native_value: %s", ex)
            return None

        return temp

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """State attributes."""
        try:
            (thermistor_id, _temp) = self.probe_manager.probe_data(self.device_serial_number).surface_sensor
        except Exception as ex:
            _LOGGER.warning("Error getting surface_sensor id for extra_state_attributes: %s", ex)
            return {}

        return {
            "thermistor_id": thermistor_id
        }


# --------------------------------------------------------------------------
# Prediction sensors (populated over a GATT connection; opt-in only)
# --------------------------------------------------------------------------

PREDICTION_STATE_DESCRIPTION = SensorEntityDescription(
    key="prediction_state",
    device_class=SensorDeviceClass.ENUM,
    options=['not_inserted', 'inserted', 'warming', 'predicting', 'removal_done'],
)

READY_IN_DESCRIPTION = SensorEntityDescription(
    key="ready_in",
    device_class=SensorDeviceClass.DURATION,
    native_unit_of_measurement="s",
)

SETPOINT_DESCRIPTION = SensorEntityDescription(
    key="prediction_setpoint",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    suggested_display_precision=1,
)


class BaseCombustionPredictionSensor(CombustionEntity, SensorEntity):
    """Base for prediction sensors, fed by the prediction manager."""

    def __init__(self, prediction_manager, serial: str) -> None:
        """Initialize."""
        super().__init__(serial)
        self.device_serial_number = serial
        # CombustionEntity wires update listeners and availability through
        # `probe_manager`; the prediction manager exposes the same interface.
        self.probe_manager = prediction_manager
        self._attr_has_entity_name = True

    def _prediction(self):
        return self.probe_manager.prediction(self.device_serial_number)

    @property
    def available(self) -> bool:
        """Available once a prediction has been received."""
        return self._prediction() is not None

    @callback
    def on_update(self):
        """Process prediction updates."""
        if self._platform_state == EntityPlatformState.ADDED:
            self.async_schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Do not poll for updates."""
        return False


class CombustionPredictionStateSensor(BaseCombustionPredictionSensor):
    """Prediction state (inserted / warming / predicting / done)."""

    def __init__(self, prediction_manager, serial: str) -> None:
        """Initialize."""
        super().__init__(prediction_manager, serial)
        self._attr_unique_id = f'{serial}--prediction-state'
        self.entity_description = PREDICTION_STATE_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Prediction'

    @property
    def native_value(self):
        """Return the prediction state."""
        p = self._prediction()
        return p.state if p else None

    @property
    def extra_state_attributes(self):
        """Prediction mode/type detail."""
        p = self._prediction()
        if p is None:
            return None
        return {'mode': p.mode, 'type': p.type}


class CombustionReadyInSensor(BaseCombustionPredictionSensor):
    """Estimated time until the probe reaches its cook target."""

    def __init__(self, prediction_manager, serial: str) -> None:
        """Initialize."""
        super().__init__(prediction_manager, serial)
        self._attr_unique_id = f'{serial}--ready-in'
        self.entity_description = READY_IN_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Ready in'

    @property
    def native_value(self):
        """Return seconds remaining, or None when not predicting."""
        p = self._prediction()
        return p.seconds_remaining if p else None


class CombustionSetpointSensor(BaseCombustionPredictionSensor):
    """Cook target (set-point) temperature."""

    def __init__(self, prediction_manager, serial: str) -> None:
        """Initialize."""
        super().__init__(prediction_manager, serial)
        self._attr_unique_id = f'{serial}--prediction-setpoint'
        self.entity_description = SETPOINT_DESCRIPTION

    @property
    def name(self):
        """Sensor name."""
        return 'Cook target'

    @property
    def native_value(self):
        """Return the set-point temperature."""
        p = self._prediction()
        return p.setpoint_c if p else None


class CombustionEstimatedCoreSensor(BaseCombustionPredictionSensor):
    """Predicted core temperature."""

    def __init__(self, prediction_manager, serial: str) -> None:
        """Initialize."""
        super().__init__(prediction_manager, serial)
        self._attr_unique_id = f'{serial}--estimated-core'
        self.entity_description = SETPOINT_DESCRIPTION
        self._attr_entity_registry_enabled_default = False

    @property
    def name(self):
        """Sensor name."""
        return 'Estimated core'

    @property
    def native_value(self):
        """Return the estimated core temperature."""
        p = self._prediction()
        return p.estimated_core_c if p else None
