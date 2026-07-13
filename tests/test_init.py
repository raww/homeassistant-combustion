"""Test initialization."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.combustion.const import DOMAIN
from tests.utils.bt_utils import (
    create_advertisement,
    create_combustion_bits,
    inject_bt_advertisement,
)


async def _setup_config_entry(hass: HomeAssistant, mock_entry: MockConfigEntry):
    mock_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    entry = config_entries[0]

    return entry

@pytest.mark.asyncio
async def test_entity_creation(hass: HomeAssistant):
    """Verify that entities are created in response to a BT advertisement."""

    mock_entry = MockConfigEntry(
        unique_id="test_entity_creation",
        domain=DOMAIN,
        version=1,
        data={
        },
        title="Meatnet",
    )

    entry = await _setup_config_entry(hass, mock_entry)

    er = entity_registry.async_get(hass)
    entities = entity_registry.async_entries_for_config_entry(er, entry.entry_id)
    assert len(entities) == 0

    inject_bt_advertisement(hass, create_advertisement(create_combustion_bits()))
    await hass.async_block_till_done()

    entities = entity_registry.async_entries_for_config_entry(er, entry.entry_id)
    sensors = [e for e in entities if e.domain == 'sensor']
    disabled_sensors = [e for e in sensors if e.disabled is True]
    binary_sensors = [e for e in entities if e.domain == 'binary_sensor']

    assert len(entities) == 13
    assert len(sensors) == 12
    # 9 disabled by default: 8 temperature sensors, and 1 RSSI sensor
    assert len(disabled_sensors) == 9
    assert len(binary_sensors) == 1


@pytest.mark.asyncio
async def test_entity_creation_non_connectable(hass: HomeAssistant):
    """Verify entities are created from a non-connectable advertisement.

    Passive Bluetooth proxies (e.g. Shelly devices) relay advertisements with
    connectable=False; the integration must still process them.
    """

    mock_entry = MockConfigEntry(
        unique_id="test_entity_creation_non_connectable",
        domain=DOMAIN,
        version=1,
        data={
        },
        title="Meatnet",
    )

    entry = await _setup_config_entry(hass, mock_entry)

    er = entity_registry.async_get(hass)

    inject_bt_advertisement(hass, create_advertisement(create_combustion_bits(), connectable=False))
    await hass.async_block_till_done()

    entities = entity_registry.async_entries_for_config_entry(er, entry.entry_id)
    assert len(entities) == 13


def _booster_bits() -> bytes:
    """Real Booster advertisement payload (product type 5)."""
    return bytes.fromhex('0543523130303034304138' + '00' * 11)


def _gauge_bits(
        serial: str = 'CR100040A8',
        temperature: float = 25.0,
        sensor_present: bool = True,
        overheating: bool = False,
        battery_low: bool = False,
        high_alarm_set: bool = False,
        high_alarm_temperature: float = 100.0,
) -> bytes:
    """Build a Gauge advertisement payload (product type 3) per the BLE spec."""
    flags = (1 if sensor_present else 0) | ((1 if overheating else 0) << 1) | ((1 if battery_low else 0) << 2)
    raw_temp = int((temperature + 20.0) / 0.1) & 0x1FFF
    high_alarm = 0
    if high_alarm_set:
        high_alarm = 0x1 | ((int((high_alarm_temperature + 20.0) / 0.1) & 0x1FFF) << 3)
    return (
        bytes([0x03])
        + serial.encode('ascii').ljust(10, b'\x00')
        + raw_temp.to_bytes(2, 'little')
        + bytes([flags])
        + b'\x00'
        + high_alarm.to_bytes(4, 'little')
        + b'\x00'
        + b'\x00'
    )


@pytest.mark.asyncio
async def test_booster_advertisement_ignored(hass: HomeAssistant):
    """Booster (product type 5) advertisements must be ignored without errors."""

    mock_entry = MockConfigEntry(
        unique_id="test_booster_ignored",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    entry = await _setup_config_entry(hass, mock_entry)

    inject_bt_advertisement(hass, create_advertisement(_booster_bits(), connectable=False))
    await hass.async_block_till_done()

    er = entity_registry.async_get(hass)
    entities = entity_registry.async_entries_for_config_entry(er, entry.entry_id)
    assert len(entities) == 0


@pytest.mark.asyncio
async def test_gauge_entity_creation(hass: HomeAssistant):
    """Gauge (product type 3) advertisements create gauge entities."""

    mock_entry = MockConfigEntry(
        unique_id="test_gauge_entity_creation",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    entry = await _setup_config_entry(hass, mock_entry)

    inject_bt_advertisement(
        hass,
        create_advertisement(
            _gauge_bits(temperature=25.0, high_alarm_set=True, high_alarm_temperature=100.0),
            connectable=False,
        ),
    )
    await hass.async_block_till_done()

    er = entity_registry.async_get(hass)
    entities = entity_registry.async_entries_for_config_entry(er, entry.entry_id)

    # 1 temperature + 1 rssi (disabled) + 5 binary sensors
    assert len(entities) == 7

    temp_entity = next(e for e in entities if e.unique_id.endswith('--gauge-temperature'))
    state = hass.states.get(temp_entity.entity_id)
    assert state is not None
    assert float(state.state) == 25.0

    alarm_entity = next(e for e in entities if e.unique_id.endswith('--high-alarm'))
    alarm_state = hass.states.get(alarm_entity.entity_id)
    assert alarm_state is not None
    assert alarm_state.state == 'off'
    assert alarm_state.attributes['set'] is True
    assert alarm_state.attributes['alarm_temperature'] == 100.0


@pytest.mark.asyncio
async def test_gauge_without_sensor_reports_no_temperature(hass: HomeAssistant):
    """A gauge with no sensor attached must report an unknown temperature, not -20."""

    mock_entry = MockConfigEntry(
        unique_id="test_gauge_no_sensor",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    await _setup_config_entry(hass, mock_entry)

    inject_bt_advertisement(
        hass,
        create_advertisement(_gauge_bits(sensor_present=False), connectable=False),
    )
    await hass.async_block_till_done()

    er = entity_registry.async_get(hass)
    entries = er.entities
    temp_entities = [e for e in entries.values() if (e.unique_id or '').endswith('--gauge-temperature')]
    assert len(temp_entities) == 1
    state = hass.states.get(temp_entities[0].entity_id)
    assert state.state == 'unknown'


@pytest.mark.asyncio
async def test_update_notifications_are_throttled(hass: HomeAssistant):
    """Repeated advertisements within the throttle window must not re-notify listeners."""
    from unittest.mock import patch

    from custom_components.combustion.probe_manager import ProbeManager

    manager = ProbeManager(bt_listener=None)
    manager.init_sensor_platform(lambda pm, data: None)
    manager.init_binary_sensor_platform(lambda pm, data: None)

    notifications = []
    manager.add_update_listener(lambda: notifications.append(1))
    update = manager.create_update_callback()

    class FakeData:
        serial_number = 'abc123'
        device_type = 'PROBE'

    with patch('custom_components.combustion.probe_manager.time.monotonic') as monotonic:
        monotonic.return_value = 100.0
        update(FakeData())  # new device -> notify
        update(FakeData())  # within window -> suppressed
        update(FakeData())  # within window -> suppressed
        assert len(notifications) == 1

        monotonic.return_value = 101.1  # past the 1s window
        update(FakeData())
        assert len(notifications) == 2


@pytest.mark.asyncio
async def test_listener_removed_with_entity(hass: HomeAssistant):
    """Entity listeners must be deregistered when entities are removed (no leak)."""

    mock_entry = MockConfigEntry(
        unique_id="test_listener_cleanup",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    entry = await _setup_config_entry(hass, mock_entry)

    # The first advertisement for a new address records it on the config entry,
    # which reloads the integration once (fresh ProbeManager). Inject a second
    # advertisement afterwards so entities exist under the current manager.
    inject_bt_advertisement(hass, create_advertisement(create_combustion_bits()))
    await hass.async_block_till_done()
    probe_manager = hass.data[DOMAIN]
    inject_bt_advertisement(hass, create_advertisement(create_combustion_bits()))
    await hass.async_block_till_done()

    assert hass.data[DOMAIN] is probe_manager, "known address must not reload the entry again"
    listeners_while_loaded = len(probe_manager._listeners)
    assert listeners_while_loaded > 0

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert len(probe_manager._listeners) == 0


@pytest.mark.asyncio
async def test_entities_become_unavailable_when_device_stops_advertising(hass: HomeAssistant):
    """Entities must go unavailable after the availability timeout (issue #44)."""
    import time as real_time
    from datetime import timedelta
    from unittest.mock import patch

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    mock_entry = MockConfigEntry(
        unique_id="test_availability",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    await _setup_config_entry(hass, mock_entry)

    inject_bt_advertisement(hass, create_advertisement(create_combustion_bits(temperature_data=[25.0] * 8)))
    await hass.async_block_till_done()

    er = entity_registry.async_get(hass)
    core_entities = [e for e in er.entities.values() if (e.unique_id or '').endswith('--sensor--core')]
    assert len(core_entities) == 1
    entity_id = core_entities[0].entity_id

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state not in ('unavailable', 'unknown')

    # Simulate 120s of silence, then let the periodic availability check fire.
    with patch(
        'custom_components.combustion.probe_manager.time.monotonic',
        return_value=real_time.monotonic() + 120.0,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == 'unavailable'


@pytest.mark.asyncio
async def test_direct_data_preferred_over_repeated(hass: HomeAssistant):
    """Node-repeated data must not overwrite fresh direct probe data."""
    from unittest.mock import patch

    from custom_components.combustion.probe_manager import ProbeManager

    manager = ProbeManager(bt_listener=None)
    manager.init_sensor_platform(lambda pm, data: None)
    manager.init_binary_sensor_platform(lambda pm, data: None)
    update = manager.create_update_callback()

    class Data:
        def __init__(self, device_type, tag):
            self.serial_number = 'abc123'
            self.device_type = device_type
            self.tag = tag

    with patch('custom_components.combustion.probe_manager.time.monotonic') as monotonic:
        monotonic.return_value = 100.0
        update(Data('PROBE', 'direct-1'))
        update(Data('MEAT_NET_NODE', 'repeat-1'))  # fresh direct data exists -> ignored
        assert manager.probe_data('abc123').tag == 'direct-1'

        monotonic.return_value = 106.0  # direct data now stale (>5s)
        update(Data('MEAT_NET_NODE', 'repeat-2'))
        assert manager.probe_data('abc123').tag == 'repeat-2'

        monotonic.return_value = 107.0
        update(Data('PROBE', 'direct-2'))
        assert manager.probe_data('abc123').tag == 'direct-2'
