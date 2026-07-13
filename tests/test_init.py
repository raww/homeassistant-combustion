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

    assert len(entities) == 18
    assert len(sensors) == 14
    # 9 disabled by default: 8 temperature sensors, and 1 RSSI sensor
    assert len(disabled_sensors) == 9
    assert len(binary_sensors) == 4


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
    assert len(entities) == 18


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


@pytest.mark.asyncio
async def test_instant_read_sensor(hass: HomeAssistant):
    """Instant-read adverts feed the instant read sensor without clobbering normal data."""
    import time as real_time
    from unittest.mock import patch

    from custom_components.combustion.combustion_ble.mode_id import ProbeMode

    mock_entry = MockConfigEntry(
        unique_id="test_instant_read",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    await _setup_config_entry(hass, mock_entry)

    normal = create_combustion_bits(temperature_data=[25.0] * 8)
    # First advert triggers the one-time entry reload; re-inject afterwards.
    inject_bt_advertisement(hass, create_advertisement(normal))
    await hass.async_block_till_done()
    inject_bt_advertisement(hass, create_advertisement(normal))
    await hass.async_block_till_done()

    er = entity_registry.async_get(hass)
    instant_id = next(e.entity_id for e in er.entities.values() if (e.unique_id or '').endswith('--sensor--instant-read'))
    core_id = next(e.entity_id for e in er.entities.values() if (e.unique_id or '').endswith('--sensor--core'))

    assert hass.states.get(instant_id).state == 'unknown'
    assert float(hass.states.get(core_id).state) == 25.0

    instant = create_combustion_bits(
        mode=ProbeMode.instantRead.value,
        temperature_data=[85.0] + [25.0] * 7,
    )
    # Advance past the notify throttle window for this device.
    with patch(
        'custom_components.combustion.probe_manager.time.monotonic',
        return_value=real_time.monotonic() + 10.0,
    ):
        inject_bt_advertisement(hass, create_advertisement(instant))
        await hass.async_block_till_done()

        assert float(hass.states.get(instant_id).state) == 85.0
        # Normal-mode readings must be preserved.
        assert float(hass.states.get(core_id).state) == 25.0


@pytest.mark.asyncio
async def test_mode_and_overheating_sensors(hass: HomeAssistant):
    """Mode diagnostic sensor and overheating binary sensor reflect the advert."""
    import time as real_time
    from unittest.mock import patch

    mock_entry = MockConfigEntry(
        unique_id="test_mode_overheat",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    await _setup_config_entry(hass, mock_entry)

    normal = create_advertisement(create_combustion_bits())
    inject_bt_advertisement(hass, normal)
    await hass.async_block_till_done()
    inject_bt_advertisement(hass, normal)
    await hass.async_block_till_done()

    er = entity_registry.async_get(hass)
    mode_id = next(e.entity_id for e in er.entities.values() if (e.unique_id or '').endswith('--mode'))
    overheat_id = next(e.entity_id for e in er.entities.values() if (e.unique_id or '').endswith('--overheating'))

    mode_state = hass.states.get(mode_id)
    assert mode_state.state == 'normal'
    assert mode_state.attributes['probe_id'] == 1
    assert mode_state.attributes['color'] == 'yellow'

    assert hass.states.get(overheat_id).state == 'off'

    # T2 and T8 overheating
    hot = create_advertisement(create_combustion_bits(overheating_mask=0b10000010))
    with patch(
        'custom_components.combustion.probe_manager.time.monotonic',
        return_value=real_time.monotonic() + 10.0,
    ):
        inject_bt_advertisement(hass, hot)
        await hass.async_block_till_done()

        overheat_state = hass.states.get(overheat_id)
        assert overheat_state.state == 'on'
        assert overheat_state.attributes['overheating_sensors'] == [2, 8]


@pytest.mark.asyncio
async def test_cooking_sensor_hysteresis(hass: HomeAssistant):
    """Cooking sensor turns on at >=45C ambient and off below 40C."""
    import time as real_time
    from unittest.mock import patch

    mock_entry = MockConfigEntry(
        unique_id="test_cooking",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    await _setup_config_entry(hass, mock_entry)

    def temps(ambient):
        # Default ambient virtual sensor is T7 (index 6).
        values = [25.0] * 8
        values[6] = ambient
        return values

    cold = create_advertisement(create_combustion_bits(temperature_data=temps(25.0)))
    inject_bt_advertisement(hass, cold)
    await hass.async_block_till_done()
    inject_bt_advertisement(hass, cold)
    await hass.async_block_till_done()

    er = entity_registry.async_get(hass)
    cooking_id = next(e.entity_id for e in er.entities.values() if (e.unique_id or '').endswith('--cooking'))
    mode_id = next(e.entity_id for e in er.entities.values() if (e.unique_id or '').endswith('--mode'))

    assert hass.states.get(cooking_id).state == 'off'

    # Source attributes exposed on the mode sensor
    mode_attrs = hass.states.get(mode_id).attributes
    assert mode_attrs['via_repeater'] is False
    assert mode_attrs['hops'] is None
    assert 'source_address' in mode_attrs

    base = real_time.monotonic()
    with patch('custom_components.combustion.probe_manager.time.monotonic', return_value=base + 10.0):
        inject_bt_advertisement(hass, create_advertisement(create_combustion_bits(temperature_data=temps(80.0))))
        await hass.async_block_till_done()
        state = hass.states.get(cooking_id)
        assert state.state == 'on'
        assert state.attributes['ambient_temperature'] == 80.0

    with patch('custom_components.combustion.probe_manager.time.monotonic', return_value=base + 20.0):
        # 42C: below the ON threshold but above the OFF threshold -> stays on
        inject_bt_advertisement(hass, create_advertisement(create_combustion_bits(temperature_data=temps(42.0))))
        await hass.async_block_till_done()
        assert hass.states.get(cooking_id).state == 'on'

    with patch('custom_components.combustion.probe_manager.time.monotonic', return_value=base + 30.0):
        inject_bt_advertisement(hass, create_advertisement(create_combustion_bits(temperature_data=temps(30.0))))
        await hass.async_block_till_done()
        assert hass.states.get(cooking_id).state == 'off'


@pytest.mark.asyncio
async def test_manager_options_respected(hass: HomeAssistant):
    """Configured availability timeout and update throttle are honored."""
    from unittest.mock import patch

    from custom_components.combustion.probe_manager import ProbeManager

    manager = ProbeManager(
        bt_listener=None,
        availability_timeout_seconds=20.0,
        min_notify_interval_seconds=5.0,
    )
    manager.init_sensor_platform(lambda pm, data: None)
    manager.init_binary_sensor_platform(lambda pm, data: None)

    notifications = []
    manager.add_update_listener(lambda: notifications.append(1))
    update = manager.create_update_callback()

    class FakeData:
        serial_number = 'opt123'
        device_type = 'PROBE'

    with patch('custom_components.combustion.probe_manager.time.monotonic') as monotonic:
        monotonic.return_value = 100.0
        update(FakeData())
        monotonic.return_value = 102.0  # under the 5s throttle
        update(FakeData())
        assert len(notifications) == 1
        monotonic.return_value = 105.5  # past the 5s throttle
        update(FakeData())
        assert len(notifications) == 2

        monotonic.return_value = 120.0  # 14.5s since last advert < 20s timeout
        assert manager.device_available('opt123') is True
        monotonic.return_value = 126.0  # 20.5s since last advert > 20s timeout
        assert manager.device_available('opt123') is False


@pytest.mark.asyncio
async def test_options_flow(hass: HomeAssistant):
    """The options flow stores availability timeout and update throttle."""

    mock_entry = MockConfigEntry(
        unique_id="test_options_flow",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    entry = await _setup_config_entry(hass, mock_entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result['type'] == 'form'
    assert result['step_id'] == 'init'

    result = await hass.config_entries.options.async_configure(
        result['flow_id'],
        user_input={'availability_timeout': 30, 'update_throttle': 2.5},
    )
    assert result['type'] == 'create_entry'
    await hass.async_block_till_done()

    assert entry.options['availability_timeout'] == 30
    assert entry.options['update_throttle'] == 2.5

    # The reload triggered by the options update applies them to the manager.
    manager = hass.data[DOMAIN]
    assert manager.availability_timeout_seconds == 30.0
    assert manager.min_notify_interval_seconds == 2.5


@pytest.mark.asyncio
async def test_probe_inserted_detects_fridge_cold_meat(hass: HomeAssistant):
    """Cold meat at room temperature reads as inserted (differential) but not cooking."""
    import time as real_time
    from unittest.mock import patch

    mock_entry = MockConfigEntry(
        unique_id="test_inserted",
        domain=DOMAIN,
        version=1,
        data={},
        title="Meatnet",
    )

    await _setup_config_entry(hass, mock_entry)

    uniform = create_advertisement(create_combustion_bits(temperature_data=[20.0] * 8))
    inject_bt_advertisement(hass, uniform)
    await hass.async_block_till_done()
    inject_bt_advertisement(hass, uniform)
    await hass.async_block_till_done()

    er = entity_registry.async_get(hass)
    inserted_id = next(e.entity_id for e in er.entities.values() if (e.unique_id or '').endswith('--inserted'))
    cooking_id = next(e.entity_id for e in er.entities.values() if (e.unique_id or '').endswith('--cooking'))

    # Probe on the counter: uniform temperatures -> not inserted.
    assert hass.states.get(inserted_id).state == 'off'

    base = real_time.monotonic()
    # Into fridge-cold meat on the counter: tip 4C, handle 20C.
    fridge_meat = create_advertisement(create_combustion_bits(temperature_data=[4.0] + [20.0] * 7))
    with patch('custom_components.combustion.probe_manager.time.monotonic', return_value=base + 10.0):
        inject_bt_advertisement(hass, fridge_meat)
        await hass.async_block_till_done()
        state = hass.states.get(inserted_id)
        assert state.state == 'on'
        assert state.attributes['differential'] == 16.0
        assert hass.states.get(cooking_id).state == 'off'

    # Resting: hot core, room ambient -> still inserted, not cooking.
    resting = create_advertisement(create_combustion_bits(temperature_data=[60.0] + [22.0] * 7))
    with patch('custom_components.combustion.probe_manager.time.monotonic', return_value=base + 20.0):
        inject_bt_advertisement(hass, resting)
        await hass.async_block_till_done()
        assert hass.states.get(inserted_id).state == 'on'
        assert hass.states.get(cooking_id).state == 'off'
