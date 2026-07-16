# UART Active Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Home Assistant write settings (target temp, mode, alarms, identity, power mode, resets) to Combustion probes and the gauge over the BLE UART service.

**Architecture:** Connection ownership moves out of `PredictionManager` into a new `ConnectionManager` that owns per-probe `BleakClient` lifecycle. Predictions (notify-read) and a new `ControlManager` (UART writes) become consumers of it. A pure `uart.py` module builds/parses the framed messages. Writable settings surface as HA `number`/`select`/`button` entities behind one active-connection opt-in.

**Tech Stack:** Python 3.10+, Home Assistant custom integration, `bleak` / `bleak_retry_connector`, pytest + pytest-homeassistant-custom-component.

## Global Constraints

- Runtime must not depend on `bitstring`/`bitarray` (removed for HA 2026.3 / Python 3.14). Pure-Python bit ops only.
- Everything here lives behind `CONF_ENABLE_ACTIVE_CONNECTION`, off by default. No passive-proxy path — writes need `connectable=True`.
- Run tests with `PYENV_VERSION=3.10.14 poetry run pytest -q --no-cov`; lint with `PYENV_VERSION=3.10.14 poetry run ruff check custom_components tests`. Both must pass before each commit.
- All new public functions/classes/tests need docstrings (ruff D-rules are enforced).
- Frame byte order (verified against combustion-android-ble reference): sync `CA FE`, then CRC-16/CCITT-FALSE **little-endian** at offset 2, computed over `type + payload_length + payload`.
- CRC-16/CCITT-FALSE: poly `0x1021`, init `0xFFFF`, no input/output reflection, no final XOR. Check value: `crc16_ccitt(b"123456789") == 0x29B1`.

---

## Phase A — UART protocol (pure, no BLE)

### Task 1: CRC + frame builder/parser

**Files:**
- Create: `custom_components/combustion/combustion_ble/uart.py`
- Test: `tests/test_uart.py`

**Interfaces:**
- Produces:
  - `crc16_ccitt(data: bytes) -> int`
  - `build_request(msg_type: int, payload: bytes) -> bytes`
  - `Response` NamedTuple: `msg_type: int`, `success: bool`, `payload: bytes`
  - `parse_response(data: bytes) -> Response | None`  (None on bad sync/CRC/short)

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the Combustion BLE UART framing."""
from combustion.combustion_ble.uart import (
    build_request,
    crc16_ccitt,
    parse_response,
)


def test_crc_check_value():
    """CRC-16/CCITT-FALSE check string yields 0x29B1."""
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_build_request_set_prediction_vector():
    """Set Prediction 60.0C / mode 2 matches the reference frame."""
    # payload = little-endian uint16 of (600 & 0x3FF) | (2 << 10) = 0x0A58
    frame = build_request(0x05, bytes([0x58, 0x0A]))
    assert frame.hex() == "cafeb9700502580a"


def test_build_request_zero_payload():
    """A no-payload command (silence, 0x0C) frames correctly."""
    assert build_request(0x0C, b"").hex() == "cafe62580c00"


def test_parse_response_roundtrip_success():
    """A well-formed success response parses back to its fields."""
    # Build a response frame: CA FE crc type success len payload
    payload = bytes([0x11, 0x22])
    body = bytes([0x05, 0x01, len(payload)]) + payload  # type, success=1, len, payload
    crc = crc16_ccitt(body)
    frame = bytes([0xCA, 0xFE, crc & 0xFF, (crc >> 8) & 0xFF]) + body
    resp = parse_response(frame)
    assert resp is not None
    assert resp.msg_type == 0x05
    assert resp.success is True
    assert resp.payload == payload


def test_parse_response_rejects_bad_sync():
    """A frame without the CA FE sync is rejected."""
    assert parse_response(bytes([0x00, 0x00, 0, 0, 5, 1, 0])) is None


def test_parse_response_rejects_bad_crc():
    """A frame whose CRC does not match is rejected."""
    body = bytes([0x05, 0x01, 0x00])
    frame = bytes([0xCA, 0xFE, 0x00, 0x00]) + body  # deliberately wrong CRC
    assert parse_response(frame) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_uart.py -q --no-cov`
Expected: FAIL (module `uart` does not exist).

- [ ] **Step 3: Write the implementation**

```python
"""Combustion BLE UART message framing.

Request:  CA FE | CRC(2, LE) | type(1) | len(1) | payload
Response: CA FE | CRC(2, LE) | type(1) | success(1) | len(1) | payload

CRC is CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no xorout)
over type + len + payload (request) or type + success + len + payload (response).
Verified against combustion-inc/combustion-android-ble.
"""
from __future__ import annotations

from typing import NamedTuple

SYNC = bytes([0xCA, 0xFE])
REQUEST_HEADER_SIZE = 6
RESPONSE_HEADER_SIZE = 7


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE over the given bytes."""
    crc = 0xFFFF
    for byte in data:
        for i in range(8):
            bit = (byte >> (7 - i)) & 1
            c15 = (crc >> 15) & 1
            crc = (crc << 1) & 0xFFFF
            if c15 ^ bit:
                crc ^= 0x1021
    return crc & 0xFFFF


def build_request(msg_type: int, payload: bytes) -> bytes:
    """Frame a request message with sync bytes and CRC."""
    body = bytes([msg_type, len(payload)]) + payload
    crc = crc16_ccitt(body)
    return SYNC + bytes([crc & 0xFF, (crc >> 8) & 0xFF]) + body


class Response(NamedTuple):
    """A parsed UART response message."""

    msg_type: int
    success: bool
    payload: bytes


def parse_response(data: bytes) -> Response | None:
    """Parse and validate a response frame, or None if malformed."""
    if len(data) < RESPONSE_HEADER_SIZE or data[0:2] != SYNC:
        return None
    msg_type = data[4]
    success = data[5] > 0
    length = data[6]
    if len(data) < RESPONSE_HEADER_SIZE + length:
        return None
    crc_body = data[4:7 + length]  # type + success + len + payload
    sent_crc = data[2] | (data[3] << 8)
    if crc16_ccitt(crc_body) != sent_crc:
        return None
    return Response(msg_type=msg_type, success=success, payload=bytes(data[7:7 + length]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_uart.py -q --no-cov`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint and commit**

```bash
PYENV_VERSION=3.10.14 poetry run ruff check custom_components/combustion/combustion_ble/uart.py tests/test_uart.py
git add custom_components/combustion/combustion_ble/uart.py tests/test_uart.py
git commit -m "Add Combustion UART message framing (CRC + build/parse)"
```

---

### Task 2: Simple command builders

**Files:**
- Modify: `custom_components/combustion/combustion_ble/uart.py`
- Test: `tests/test_uart.py`

**Interfaces:**
- Consumes: `build_request` (Task 1)
- Produces (all return framed `bytes`):
  - `MessageType` IntEnum with the values below
  - `PredictionMode` IntEnum: `NONE=0, TIME_TO_REMOVAL=1, REMOVAL_AND_RESTING=2`
  - `PowerMode` IntEnum: `NORMAL=0, ALWAYS_ON=1`
  - `set_prediction(setpoint_c: float, mode: PredictionMode) -> bytes`
  - `silence_alarms() -> bytes`
  - `set_power_mode(mode: PowerMode) -> bytes`
  - `set_probe_id(probe_id: int) -> bytes`   (0-7)
  - `set_probe_colour(colour: int) -> bytes` (0-7)
  - `reset_probe() -> bytes`
  - `reset_food_safe() -> bytes`

Message type IDs (verified vs reference): SET_PROBE_ID=0x01, SET_PROBE_COLOR=0x02, SET_PREDICTION=0x05, RESET_FOOD_SAFE=0x08, SET_POWER_MODE=0x09, RESET_PROBE=0x0A, SET_PROBE_HIGH_LOW_ALARM=0x0B, SILENCE_PROBE_ALARMS=0x0C.

- [ ] **Step 1: Write the failing tests**

```python
def test_set_prediction_packs_setpoint_and_mode():
    """Set Prediction packs setpoint (0.1C, 10-bit) | mode << 10, LE."""
    from combustion.combustion_ble.uart import PredictionMode, set_prediction
    frame = set_prediction(60.0, PredictionMode.REMOVAL_AND_RESTING)
    assert frame.hex() == "cafeb9700502580a"


def test_set_prediction_clamps_setpoint():
    """Setpoints above 102.3C clamp to the 10-bit maximum."""
    from combustion.combustion_ble.uart import PredictionMode, set_prediction
    from combustion.combustion_ble.uart import parse_request_payload_word
    frame = set_prediction(200.0, PredictionMode.NONE)
    # payload word low 10 bits == 0x3FF
    word = frame[6] | (frame[7] << 8)
    assert (word & 0x3FF) == 0x3FF


def test_silence_alarms_frame():
    """Silence alarms is a no-payload 0x0C command."""
    from combustion.combustion_ble.uart import silence_alarms
    assert silence_alarms().hex() == "cafe62580c00"


def test_set_power_mode_payload():
    """Set Power Mode carries a single mode byte."""
    from combustion.combustion_ble.uart import PowerMode, set_power_mode
    frame = set_power_mode(PowerMode.ALWAYS_ON)
    assert frame[4] == 0x09 and frame[5] == 0x01 and frame[6] == 0x01


def test_set_probe_id_and_colour_payload():
    """Set Probe ID / Colour carry a single 0-7 byte."""
    from combustion.combustion_ble.uart import set_probe_colour, set_probe_id
    assert set_probe_id(3)[4] == 0x01 and set_probe_id(3)[6] == 0x03
    assert set_probe_colour(5)[4] == 0x02 and set_probe_colour(5)[6] == 0x05


def test_reset_commands_have_no_payload():
    """Reset probe / food safe are no-payload commands."""
    from combustion.combustion_ble.uart import reset_food_safe, reset_probe
    assert reset_probe()[4] == 0x0A and reset_probe()[5] == 0x00
    assert reset_food_safe()[4] == 0x08 and reset_food_safe()[5] == 0x00
```

- [ ] **Step 2: Run to verify failure**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_uart.py -q --no-cov -k "prediction or silence or power or probe_id or reset"`
Expected: FAIL (names not defined).

- [ ] **Step 3: Implement (append to `uart.py`)**

```python
from enum import IntEnum


class MessageType(IntEnum):
    """UART request message type IDs."""

    SET_PROBE_ID = 0x01
    SET_PROBE_COLOR = 0x02
    SET_PREDICTION = 0x05
    RESET_FOOD_SAFE = 0x08
    SET_POWER_MODE = 0x09
    RESET_PROBE = 0x0A
    SET_PROBE_HIGH_LOW_ALARM = 0x0B
    SILENCE_PROBE_ALARMS = 0x0C


class PredictionMode(IntEnum):
    """Prediction input mode (2-bit field)."""

    NONE = 0
    TIME_TO_REMOVAL = 1
    REMOVAL_AND_RESTING = 2


class PowerMode(IntEnum):
    """Probe power mode."""

    NORMAL = 0
    ALWAYS_ON = 1


def parse_request_payload_word(frame: bytes) -> int:
    """Return the little-endian uint16 payload word of a request (test helper)."""
    return frame[6] | (frame[7] << 8)


def set_prediction(setpoint_c: float, mode: PredictionMode) -> bytes:
    """Build a Set Prediction command."""
    converted = int(round(setpoint_c * 10.0))
    clamped = min(max(converted, 0), 0x3FF)
    word = (clamped & 0x3FF) | (int(mode) << 10)
    payload = bytes([word & 0xFF, (word >> 8) & 0xFF])
    return build_request(MessageType.SET_PREDICTION, payload)


def silence_alarms() -> bytes:
    """Build a Silence Alarms command."""
    return build_request(MessageType.SILENCE_PROBE_ALARMS, b"")


def set_power_mode(mode: PowerMode) -> bytes:
    """Build a Set Power Mode command."""
    return build_request(MessageType.SET_POWER_MODE, bytes([int(mode)]))


def set_probe_id(probe_id: int) -> bytes:
    """Build a Set Probe ID command (0-7)."""
    return build_request(MessageType.SET_PROBE_ID, bytes([probe_id & 0x07]))


def set_probe_colour(colour: int) -> bytes:
    """Build a Set Probe Colour command (0-7)."""
    return build_request(MessageType.SET_PROBE_COLOR, bytes([colour & 0x07]))


def reset_probe() -> bytes:
    """Build a Reset Thermometer command (wipes the cook session)."""
    return build_request(MessageType.RESET_PROBE, b"")


def reset_food_safe() -> bytes:
    """Build a Reset Food Safe command."""
    return build_request(MessageType.RESET_FOOD_SAFE, b"")
```

- [ ] **Step 4: Run to verify pass**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_uart.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
PYENV_VERSION=3.10.14 poetry run ruff check custom_components/combustion/combustion_ble/uart.py tests/test_uart.py
git add custom_components/combustion/combustion_ble/uart.py tests/test_uart.py
git commit -m "Add simple UART command builders (prediction, power, id, colour, silence, resets)"
```

---

## Phase B — Connection ownership

### Task 3: `ConnectionManager` (extract connection code from `PredictionManager`)

**Files:**
- Create: `custom_components/combustion/connection_manager.py`
- Test: `tests/test_connection_manager.py`

**Interfaces:**
- Consumes: `bluetooth` helpers, `bleak`, `parse_response`/`build_request` (for send).
- Produces:
  - `class ConnectionManager` with:
    - `__init__(self, hass, entry, probe_manager, enabled: bool)`
    - `async_init() -> None`  (registers connectable advert callback when enabled)
    - `subscribe(self, char_uuid: str, handler) -> None`  (handler: `(serial, data: bytes) -> None`)
    - `add_connection_listener(self, listener) -> Callable`  (listener: `() -> None`, returns remover)
    - `is_connected(self, serial: str) -> bool`
    - `async_send_command(self, serial: str, frame: bytes) -> Response`  (raises `HomeAssistantError` if not connectable/failed)
    - `UART_RX_CHAR = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"`

The persistent-connection loop, backoff constants, and address bookkeeping move here verbatim from `prediction_manager.py`. The new pieces are the subscribe registry, connection listeners, `is_connected`, and `async_send_command`.

- [ ] **Step 1: Write the failing tests** (fake bleak client, no hardware)

```python
"""Tests for the shared BLE ConnectionManager."""
import asyncio

import pytest
from homeassistant.exceptions import HomeAssistantError

from combustion.connection_manager import ConnectionManager


class _FakeClient:
    def __init__(self):
        self.notifications = {}
        self.written = []
        self.connected = True

    async def start_notify(self, char, handler):
        self.notifications[char] = handler

    async def write_gatt_char(self, char, data, response=True):
        self.written.append((char, bytes(data)))

    async def disconnect(self):
        self.connected = False


def _manager(hass):
    from unittest.mock import MagicMock
    entry = MagicMock()
    entry.async_on_unload = MagicMock()
    pm = MagicMock()
    return ConnectionManager(hass, entry, pm, enabled=True)


@pytest.mark.asyncio
async def test_subscribe_registers_handler_on_connect(hass):
    """A subscribed char gets start_notify called when a client connects."""
    mgr = _manager(hass)
    seen = []
    mgr.subscribe("char-a", lambda serial, data: seen.append((serial, data)))
    client = _FakeClient()
    await mgr._on_connected("SERIAL1", client)
    assert "char-a" in client.notifications
    # a notification routes to the handler with the serial
    client.notifications["char-a"](None, bytearray(b"\x01\x02"))
    assert seen == [("SERIAL1", b"\x01\x02")]


@pytest.mark.asyncio
async def test_send_command_writes_when_connected(hass):
    """async_send_command writes the frame to the UART RX char."""
    mgr = _manager(hass)
    client = _FakeClient()
    await mgr._on_connected("SERIAL1", client)
    # stub a success response by pre-seeding the response future path:
    resp = await mgr._write_and_wait(client, b"\xca\xfe\x00\x00\x0c\x00", expect=False)
    assert client.written[0][0] == ConnectionManager.UART_RX_CHAR
    assert client.written[0][1] == b"\xca\xfe\x00\x00\x0c\x00"


@pytest.mark.asyncio
async def test_send_command_raises_when_not_connected(hass):
    """async_send_command raises when the probe has no live client or address."""
    mgr = _manager(hass)
    with pytest.raises(HomeAssistantError):
        await mgr.async_send_command("UNKNOWN", b"\xca\xfe\x00\x00\x0c\x00")


@pytest.mark.asyncio
async def test_connection_listener_fires_on_state_change(hass):
    """Connect/disconnect notifies connection listeners and flips is_connected."""
    mgr = _manager(hass)
    ticks = []
    mgr.add_connection_listener(lambda: ticks.append(mgr.is_connected("SERIAL1")))
    await mgr._on_connected("SERIAL1", _FakeClient())
    assert mgr.is_connected("SERIAL1") is True
    mgr._on_disconnected("SERIAL1")
    assert mgr.is_connected("SERIAL1") is False
    assert ticks == [True, False]
```

- [ ] **Step 2: Run to verify failure**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_connection_manager.py -q --no-cov`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `connection_manager.py`**

Port the connection loop from `prediction_manager.py` and add the new seams. Key structure (the connect loop calls `_on_connected`/`_on_disconnected` so tests can drive them without bleak):

```python
"""Own per-probe connectable BLE connections; shared by predictions and control.

Requires a *connectable* path (local adapter or ESPHome active proxy). Passive
proxies cannot provide it. Opt-in via the active-connection option.
"""
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from custom_components.combustion.combustion_ble.combustion_probe_data import (
    CombustionProbeData,
)
from custom_components.combustion.combustion_ble.uart import parse_response
from custom_components.combustion.const import BT_MANUFACTURER_ID, LOGGER
from custom_components.combustion.probe_manager import ProbeManager

_LOGGER = LOGGER.getChild("connection")

RECONNECT_MIN_SECONDS = 5
RECONNECT_MAX_SECONDS = 300
WRITE_TIMEOUT = 5.0


class ConnectionManager:
    """Maintain connectable probe connections and expose subscribe/send seams."""

    UART_RX_CHAR = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, probe_manager: ProbeManager, enabled: bool) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.probe_manager = probe_manager
        self.enabled = enabled
        self._subscriptions: dict[str, Callable] = {}
        self._clients: dict[str, object] = {}
        self._addresses: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._conn_listeners: list[Callable] = []

    def async_init(self) -> None:
        """Register the connectable advert callback (only when enabled)."""
        if not self.enabled:
            return
        try:
            self.entry.async_on_unload(
                bluetooth.async_register_callback(
                    self.hass,
                    self._connectable_advertisement,
                    bluetooth.BluetoothCallbackMatcher(manufacturer_id=BT_MANUFACTURER_ID, connectable=True),
                    bluetooth.BluetoothScanningMode.ACTIVE,
                )
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Could not register connectable callback; active connection disabled", exc_info=True)
            return
        self.entry.async_on_unload(self._async_shutdown)

    def subscribe(self, char_uuid: str, handler: Callable) -> None:
        """Register a notify handler `(serial, data: bytes)` for a characteristic."""
        self._subscriptions[char_uuid] = handler

    def add_connection_listener(self, listener: Callable) -> Callable:
        """Register a listener called on any connect/disconnect. Returns remover."""
        self._conn_listeners.append(listener)

        def _remove():
            if listener in self._conn_listeners:
                self._conn_listeners.remove(listener)

        return _remove

    def is_connected(self, serial: str) -> bool:
        """Whether a live client exists for this probe serial."""
        return serial in self._clients

    def _notify_conn_listeners(self) -> None:
        for listener in list(self._conn_listeners):
            listener()

    @callback
    def _connectable_advertisement(self, service_info, change) -> None:
        payload = service_info.manufacturer_data.get(BT_MANUFACTURER_ID)
        if not payload or payload[0] != 0x01:
            return
        try:
            probe_data = CombustionProbeData.from_advertisement(service_info)
        except Exception:  # noqa: BLE001
            return
        if probe_data is None or not probe_data.valid:
            return
        serial = probe_data.serial_number
        self._addresses[serial] = service_info.address
        task = self._tasks.get(serial)
        if task is None or task.done():
            self._tasks[serial] = self.entry.async_create_background_task(
                self.hass, self._maintain_connection(serial), f"combustion-conn-{serial}"
            )

    async def _maintain_connection(self, serial: str) -> None:
        from bleak import BleakClient
        from bleak_retry_connector import establish_connection

        backoff = RECONNECT_MIN_SECONDS
        while True:
            address = self._addresses.get(serial)
            ble_device = bluetooth.async_ble_device_from_address(self.hass, address, connectable=True) if address else None
            if ble_device is None:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)
                continue
            disconnected = asyncio.Event()
            client = None
            try:
                client = await establish_connection(
                    BleakClient, ble_device, serial,
                    disconnected_callback=lambda _c, ev=disconnected: ev.set(),
                )
                backoff = RECONNECT_MIN_SECONDS
                await self._on_connected(serial, client)
                await disconnected.wait()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Connection to [%s] failed", serial, exc_info=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)
            finally:
                self._on_disconnected(serial)
                if client is not None:
                    with contextlib.suppress(Exception):
                        await client.disconnect()

    async def _on_connected(self, serial: str, client) -> None:
        """Record a live client and (re)subscribe all notify handlers."""
        self._clients[serial] = client
        for char, handler in self._subscriptions.items():
            with contextlib.suppress(Exception):
                await client.start_notify(char, self._make_notify(serial, handler))
        self._notify_conn_listeners()

    def _on_disconnected(self, serial: str) -> None:
        """Drop the live client and notify listeners."""
        if self._clients.pop(serial, None) is not None:
            self._notify_conn_listeners()

    def _make_notify(self, serial: str, handler: Callable):
        @callback
        def _cb(_char, data: bytearray) -> None:
            handler(serial, bytes(data))
        return _cb

    async def _write_and_wait(self, client, frame: bytes, expect: bool):
        """Write a frame to the UART RX char. (expect reserved for future response reads.)"""
        await client.write_gatt_char(self.UART_RX_CHAR, frame, response=True)
        return None

    async def async_send_command(self, serial: str, frame: bytes):
        """Write a UART command to a probe, raising if it is not connected."""
        client = self._clients.get(serial)
        if client is None:
            # try one on-demand connect if we know the address
            address = self._addresses.get(serial)
            if address is None:
                raise HomeAssistantError(f"{serial} is not connected")
            # ensure the maintain loop is running; give it a moment
            self._connectable_kick(serial)
            for _ in range(int(WRITE_TIMEOUT * 10)):
                await asyncio.sleep(0.1)
                client = self._clients.get(serial)
                if client is not None:
                    break
            if client is None:
                raise HomeAssistantError(f"{serial} is not connected")
        try:
            await self._write_and_wait(client, frame, expect=False)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to send command to {serial}: {err}") from err

    def _connectable_kick(self, serial: str) -> None:
        task = self._tasks.get(serial)
        if task is None or task.done():
            self._tasks[serial] = self.entry.async_create_background_task(
                self.hass, self._maintain_connection(serial), f"combustion-conn-{serial}"
            )

    async def _async_shutdown(self) -> None:
        self._conn_listeners.clear()
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._clients.clear()
```

- [ ] **Step 4: Run to verify pass**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_connection_manager.py -q --no-cov`
Expected: PASS (4 tests).

- [ ] **Step 5: Lint and commit**

```bash
PYENV_VERSION=3.10.14 poetry run ruff check custom_components/combustion/connection_manager.py tests/test_connection_manager.py
git add custom_components/combustion/connection_manager.py tests/test_connection_manager.py
git commit -m "Add shared ConnectionManager (subscribe registry, send, connection-state broadcast)"
```

---

### Task 4: Refactor `PredictionManager` into a consumer

**Files:**
- Modify: `custom_components/combustion/prediction_manager.py`
- Modify: `custom_components/combustion/__init__.py` (construct `ConnectionManager`, pass to `PredictionManager`)
- Test: existing prediction tests (must stay green)

**Interfaces:**
- Consumes: `ConnectionManager.subscribe`, `ConnectionManager.add_connection_listener`
- Produces: unchanged public surface (`prediction(serial)`, `init_sensor_platform`, `add_update_listener`)

- [ ] **Step 1: Change `PredictionManager` to take a `ConnectionManager` and subscribe**

Remove the `bleak`/`establish_connection`/`_maintain_connection`/`_connectable_advertisement`/backoff code. Replace `async_init` with:

```python
def __init__(self, hass, entry, connection_manager, probe_manager) -> None:
    """Initialize as a consumer of the shared connection."""
    self.hass = hass
    self.entry = entry
    self.connection_manager = connection_manager
    self.probe_manager = probe_manager
    self.data: dict[str, PredictionData] = {}
    self._create_sensors_callback = None
    self._listeners = []
    self._known: set[str] = set()

def async_init(self) -> None:
    """Subscribe to the Probe Status characteristic on the shared connection."""
    self.connection_manager.subscribe(PROBE_STATUS_CHAR, self._on_status)

def _on_status(self, serial: str, data: bytes) -> None:
    prediction = PredictionData.from_status_characteristic(data)
    if prediction is None:
        return
    self.data[serial] = prediction
    if serial not in self._known and self._create_sensors_callback is not None:
        self._known.add(serial)
        self._create_sensors_callback(self, serial)
    for listener in list(self._listeners):
        listener()
```

Keep `prediction()`, `init_sensor_platform()`, `add_update_listener()` unchanged.

- [ ] **Step 2: Update `__init__.py` construction order**

In `async_setup_entry`, read the opt-in (still `CONF_ENABLE_PREDICTIONS` until Task 5), then:

```python
connection_manager = ConnectionManager(hass, entry, probe_manager, enabled=active_enabled)
prediction_manager = PredictionManager(hass, entry, connection_manager, probe_manager)
prediction_manager.async_init()
connection_manager.async_init()
# Expose the managers to the entity platforms. The existing code stores the
# ProbeManager at hass.data[DOMAIN]; attach the new managers + flag to it so the
# control platforms can reach them (Task 13 adds the number/select/button setup).
probe_manager.connection_manager = connection_manager
probe_manager.control_manager = None  # set in Task 6/13
probe_manager.active_enabled = active_enabled
```

(Reuse the object already stored at `hass.data[DOMAIN]` — currently the `ProbeManager` — as the container the platforms read, rather than introducing a new key. Task 13 sets `control_manager` once `ControlManager` exists.)

- [ ] **Step 3: Run the full suite**

Run: `PYENV_VERSION=3.10.14 poetry run pytest -q --no-cov`
Expected: PASS — prediction tests still green with the connection now owned by `ConnectionManager`.

- [ ] **Step 4: Lint and commit**

```bash
PYENV_VERSION=3.10.14 poetry run ruff check custom_components/combustion
git add custom_components/combustion/prediction_manager.py custom_components/combustion/__init__.py
git commit -m "Refactor PredictionManager to consume the shared ConnectionManager"
```

---

## Phase C — Control + opt-in

### Task 5: Replace the opt-in flag

**Files:**
- Modify: `custom_components/combustion/const.py` (`CONF_ENABLE_ACTIVE_CONNECTION = "enable_active_connection"`; remove `CONF_ENABLE_PREDICTIONS`)
- Modify: `custom_components/combustion/config_flow.py` (options schema uses the new key + label "Active connection (predictions + control)")
- Modify: `custom_components/combustion/__init__.py` (read the new key)
- Test: `tests/test_config_flow.py`

- [ ] **Step 1: Update the options-flow test** to assert the new key name and default `False`. (Mirror the existing predictions test in `tests/test_config_flow.py`; change the key to `enable_active_connection`.)

- [ ] **Step 2: Rename in `const.py`, `config_flow.py`, `__init__.py`** — no alias, single replacement.

- [ ] **Step 3: Run the suite**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_config_flow.py -q --no-cov`
Expected: PASS.

- [ ] **Step 4: Lint and commit**

```bash
PYENV_VERSION=3.10.14 poetry run ruff check custom_components/combustion tests
git add -A
git commit -m "Replace predictions opt-in with active-connection opt-in"
```

---

### Task 6: `ControlManager`

**Files:**
- Create: `custom_components/combustion/control_manager.py`
- Test: `tests/test_control_manager.py`

**Interfaces:**
- Consumes: `ConnectionManager.async_send_command`, `uart` builders
- Produces:
  - `class ControlManager(connection_manager)` with async methods:
    - `async_set_target(serial, temp_c, mode)`, `async_set_mode(serial, mode)` (uses last-known target)
    - `async_silence(serial)`, `async_set_power_mode(serial, mode)`
    - `async_set_probe_id(serial, n)`, `async_set_probe_colour(serial, n)`
    - `async_reset_probe(serial)`, `async_reset_food_safe(serial)`
  - Tracks last-set target/mode per serial so a mode change re-sends a valid Set Prediction.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for ControlManager -> ConnectionManager wiring."""
import pytest

from combustion.combustion_ble.uart import PredictionMode
from combustion.control_manager import ControlManager


class _FakeConn:
    def __init__(self):
        self.sent = []

    async def async_send_command(self, serial, frame):
        self.sent.append((serial, frame))


@pytest.mark.asyncio
async def test_set_target_sends_prediction_frame():
    """Setting a target sends a Set Prediction frame to the right serial."""
    conn = _FakeConn()
    mgr = ControlManager(conn)
    await mgr.async_set_target("S1", 60.0, PredictionMode.REMOVAL_AND_RESTING)
    assert conn.sent[0][0] == "S1"
    assert conn.sent[0][1].hex() == "cafeb9700502580a"


@pytest.mark.asyncio
async def test_silence_sends_silence_frame():
    """Silence sends the 0x0C frame."""
    conn = _FakeConn()
    mgr = ControlManager(conn)
    await mgr.async_silence("S1")
    assert conn.sent[0][1].hex() == "cafe62580c00"
```

- [ ] **Step 2: Run to verify failure**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_control_manager.py -q --no-cov`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
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
        """Change prediction mode, keeping the last-known target temperature."""
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
```

- [ ] **Step 4: Run to verify pass**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_control_manager.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
PYENV_VERSION=3.10.14 poetry run ruff check custom_components/combustion/control_manager.py tests/test_control_manager.py
git add custom_components/combustion/control_manager.py tests/test_control_manager.py
git commit -m "Add ControlManager mapping actions to UART commands"
```

---

## Phase D — Entities

For each entity platform, follow the existing patterns in `sensor.py`/`binary_sensor.py`: `CombustionEntity` base for device grouping, `_attr_has_entity_name = True`, `EntityCategory.CONFIG`, present only when active-connection is enabled, and `available` gated on `connection_manager.is_connected(serial)`. Register the platform in `__init__.py` `PLATFORMS` (Task 11).

### Task 7: `number` platform — target temperature

**Files:**
- Create: `custom_components/combustion/number.py`
- Test: `tests/test_number.py`

**Interfaces:**
- Consumes: `ControlManager.async_set_target`, `ConnectionManager.is_connected`, `PredictionManager.prediction` (to show the current setpoint as the number's value)
- Produces: `CombustionTargetTemperature` number entity; a `_create_number_entities(...)` factory + `async_setup_entry`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the target-temperature number entity."""
import pytest

from combustion.combustion_ble.uart import PredictionMode
from combustion.number import CombustionTargetTemperature


class _Conn:
    def is_connected(self, serial):
        return True


class _Control:
    def __init__(self):
        self.calls = []

    async def async_set_target(self, serial, temp_c, mode):
        self.calls.append((serial, temp_c, mode))


class _DeviceData:
    serial_number = "S1"
    device_type = "PROBE"


@pytest.mark.asyncio
async def test_set_native_value_calls_control():
    """Setting the number sends a target to the ControlManager."""
    control = _Control()
    ent = CombustionTargetTemperature(_Conn(), control, _DeviceData(), default_mode=PredictionMode.TIME_TO_REMOVAL)
    await ent.async_set_native_value(63.0)
    assert control.calls == [("S1", 63.0, PredictionMode.TIME_TO_REMOVAL)]
```

- [ ] **Step 2: Run to verify failure**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_number.py -q --no-cov`
Expected: FAIL.

- [ ] **Step 3: Implement `number.py`**

```python
"""Number platform: writable target temperature (and alarm thresholds later)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .combustion_ble.uart import PredictionMode
from .const import DOMAIN
from .entity import CombustionEntity


class CombustionTargetTemperature(CombustionEntity, NumberEntity):
    """Writable cook target temperature (Set Prediction)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0.0
    _attr_native_max_value = 102.0
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX

    def __init__(self, connection_manager, control_manager, device_data, default_mode: PredictionMode) -> None:
        """Initialize."""
        super().__init__(device_data.serial_number)
        self._conn = connection_manager
        self._control = control_manager
        self._serial = device_data.serial_number
        self._default_mode = default_mode
        self._attr_unique_id = f"{device_data.serial_number}--target-temperature"

    @property
    def name(self):
        """Entity name."""
        return "Target temperature"

    @property
    def available(self) -> bool:
        """Only available while actively connected."""
        return self._conn.is_connected(self._serial)

    async def async_set_native_value(self, value: float) -> None:
        """Send a new target temperature to the probe."""
        await self._control.async_set_target(self._serial, value, self._default_mode)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up number entities (only when active connection is enabled)."""
    container = hass.data[DOMAIN]
    if not getattr(container, "active_enabled", False):
        return
    # Register a create-callback with the connection/control managers mirroring
    # how sensor.py registers _create_sensors_callback, adding one
    # CombustionTargetTemperature per connected probe. See Task 13 wiring.
```

(The `async_setup_entry` create-callback wiring mirrors `sensor.py`; finalize it in Task 13 when the domain container — carrying `active_enabled`, the `ConnectionManager` and `ControlManager` — is defined.)

- [ ] **Step 4: Run to verify pass**

Run: `PYENV_VERSION=3.10.14 poetry run pytest tests/test_number.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
PYENV_VERSION=3.10.14 poetry run ruff check custom_components/combustion/number.py tests/test_number.py
git add custom_components/combustion/number.py tests/test_number.py
git commit -m "Add target-temperature number entity"
```

---

### Task 8: `select` platform — mode, colour, power mode

**Files:**
- Create: `custom_components/combustion/select.py`
- Test: `tests/test_select.py`

**Interfaces:**
- Consumes: `ControlManager.async_set_mode/async_set_probe_colour/async_set_power_mode`, `is_connected`
- Produces: `CombustionModeSelect`, `CombustionColourSelect`, `CombustionPowerModeSelect`

- [ ] **Step 1: Failing test** — selecting an option calls the matching ControlManager method with the mapped value:

```python
"""Tests for the control select entities."""
import pytest

from combustion.combustion_ble.uart import PredictionMode
from combustion.select import CombustionModeSelect


class _Conn:
    def is_connected(self, serial):
        return True


class _Control:
    def __init__(self):
        self.calls = []

    async def async_set_mode(self, serial, mode):
        self.calls.append((serial, mode))


class _DeviceData:
    serial_number = "S1"
    device_type = "PROBE"


@pytest.mark.asyncio
async def test_select_mode_option_maps_to_enum():
    """Selecting a mode label sends the mapped PredictionMode."""
    control = _Control()
    ent = CombustionModeSelect(_Conn(), control, _DeviceData())
    await ent.async_select_option("Removal and resting")
    assert control.calls == [("S1", PredictionMode.REMOVAL_AND_RESTING)]
```

- [ ] **Step 2–5:** Run→fail; implement `select.py` with option→enum maps (`{"Off": NONE, "Time to removal": TIME_TO_REMOVAL, "Removal and resting": REMOVAL_AND_RESTING}`; colour `Color 1..8` → 0..7; power `Normal/Always on` → 0/1), `EntityCategory.CONFIG`, `available` gated on `is_connected`; run→pass; lint; commit `"Add mode/colour/power-mode select entities"`.

---

### Task 9: `button` platform — silence + resets

**Files:**
- Create: `custom_components/combustion/button.py`
- Test: `tests/test_button.py`

**Interfaces:**
- Consumes: `ControlManager.async_silence/async_reset_probe/async_reset_food_safe`
- Produces: `CombustionSilenceButton`, `CombustionResetProbeButton`, `CombustionResetFoodSafeButton`

Reset buttons set `_attr_entity_registry_enabled_default = False` (footgun guard).

- [ ] **Step 1: Failing test**

```python
"""Tests for the control button entities."""
import pytest

from combustion.button import CombustionResetProbeButton, CombustionSilenceButton


class _Control:
    def __init__(self):
        self.silenced = []
        self.reset = []

    async def async_silence(self, serial):
        self.silenced.append(serial)

    async def async_reset_probe(self, serial):
        self.reset.append(serial)


class _DeviceData:
    serial_number = "S1"
    device_type = "PROBE"


@pytest.mark.asyncio
async def test_silence_button_calls_control():
    """Pressing silence calls ControlManager.async_silence."""
    control = _Control()
    ent = CombustionSilenceButton(control, _DeviceData())
    await ent.async_press()
    assert control.silenced == ["S1"]


def test_reset_button_disabled_by_default():
    """The reset button is disabled by default (footgun guard)."""
    ent = CombustionResetProbeButton(_Control(), _DeviceData())
    assert ent.entity_registry_enabled_default is False
```

- [ ] **Step 2–5:** Run→fail; implement `button.py` (`ButtonEntity`, `async_press` calls the mapped method, `EntityCategory.CONFIG`, resets disabled-by-default); run→pass; lint; commit `"Add silence + reset button entities"`.

---

### Task 10: `Connected` diagnostic binary_sensor

**Files:**
- Modify: `custom_components/combustion/binary_sensor.py`
- Test: `tests/test_binary_sensor_connected.py`

**Interfaces:**
- Consumes: `ConnectionManager.is_connected`, `ConnectionManager.add_connection_listener`
- Produces: `CombustionConnectedSensor` (device_class CONNECTIVITY, diagnostic)

- [ ] **Step 1: Failing test** — `is_on` reflects `is_connected`, and the entity registers a connection listener that schedules a state update:

```python
"""Tests for the Connected diagnostic binary sensor."""
from combustion.binary_sensor import CombustionConnectedSensor


class _Conn:
    def __init__(self, connected):
        self._c = connected
        self.listeners = []

    def is_connected(self, serial):
        return self._c

    def add_connection_listener(self, listener):
        self.listeners.append(listener)
        return lambda: None


class _DeviceData:
    serial_number = "S1"
    device_type = "PROBE"


def test_connected_reflects_state():
    """is_on mirrors ConnectionManager.is_connected."""
    ent = CombustionConnectedSensor(_Conn(True), _DeviceData())
    assert ent.is_on is True
    ent2 = CombustionConnectedSensor(_Conn(False), _DeviceData())
    assert ent2.is_on is False
```

- [ ] **Step 2–5:** Run→fail; implement `CombustionConnectedSensor` (CONNECTIVITY, `EntityCategory.DIAGNOSTIC`, `is_on = conn.is_connected(serial)`, subscribes via `add_connection_listener` in `async_added_to_hass` to schedule updates); run→pass; lint; commit `"Add Connected diagnostic binary sensor"`.

---

## Phase E — Alarms (heaviest; own phase)

### Task 11: Probe high/low alarm command

**Files:**
- Modify: `custom_components/combustion/combustion_ble/uart.py`
- Test: `tests/test_uart_alarm.py`

**Context:** Port `ProbeHighLowAlarmStatus` from combustion-android-ble. Structure: 44 bytes = 11 sensors (T1–T8, virtual core, surface, ambient), each contributing a 2-byte **high** AlarmStatus in the first 22 bytes (`HIGH_ALARMS_STATUS_INDEX = 0`) and a 2-byte **low** AlarmStatus in the next 22 (`LOW_ALARMS_STATUS_INDEX = 22`). Each AlarmStatus 16-bit word: bit0 set, bit1 tripped, bit2 alarming, then the 13-bit `SensorTemperature` raw (`raw = round((temp_c + 20)/0.05)`) occupying the upper bits (`toRawDataEnd`). This is intricate — build it incrementally with computed vectors.

**Interfaces:**
- Produces: `set_probe_high_low_alarm(sensor_index: int, high_enabled: bool, high_temp_c: float, low_enabled: bool, low_temp_c: float) -> bytes` — a convenience that sets one sensor's alarms (default = the virtual **core**, index 8) and leaves the rest unset.

- [ ] **Step 1: Write a failing test with a computed vector** — assert the 44-byte payload has the right length, the target sensor's high/low words at the right offsets, and CRC valid via `parse`-style re-check. (Compute the expected word in the test from the documented packing so the test is self-checking.)
- [ ] **Step 2:** Run→fail.
- [ ] **Step 3:** Implement `AlarmStatus` word packing + `set_probe_high_low_alarm` (build a 44-byte buffer, place the two words for the chosen sensor, frame with `build_request(0x0B, payload)`).
- [ ] **Step 4:** Run→pass.
- [ ] **Step 5:** Lint; commit `"Add probe high/low alarm UART command"`.

**Note:** UX decision to confirm before wiring entities — a probe has 11 alarmable sensors. This plan defaults the HA alarm number entities to the **virtual core** sensor (what "food alarm" means in practice). The gauge (`0x61`) has a single high/low pair and is simpler. If per-sensor alarm control is wanted, that is a follow-up.

### Task 12: Alarm number entities + gauge alarm command

**Files:**
- Modify: `custom_components/combustion/number.py`, `uart.py` (gauge `0x61`)
- Test: `tests/test_number.py`, `tests/test_uart_alarm.py`

- [ ] Add `High alarm` / `Low alarm` number entities (core sensor) that call a `ControlManager.async_set_alarms(serial, high_c, low_c)` which reads current values and sends `set_probe_high_low_alarm`. Add `set_gauge_high_low_alarm` (`0x61`) and gauge variants. TDD each: failing test → implement → pass → lint → commit.

---

## Phase F — Wiring + docs

### Task 13: Wire everything in `__init__.py` + manifest

**Files:**
- Modify: `custom_components/combustion/__init__.py`, `manifest.json`, entity `async_setup_entry` create-callbacks

- [ ] Construct `ConnectionManager` + `ControlManager`; store both on the domain container the platforms read. Register per-probe create-callbacks for `number`/`select`/`button` (fired the first time a probe connects, mirroring `sensor.py`). Add `"number"`, `"select"`, `"button"` to `PLATFORMS` and `manifest.json`. Gate all control platforms on `active_enabled`.
- [ ] Run the full suite: `PYENV_VERSION=3.10.14 poetry run pytest -q --no-cov` → PASS. Lint. Commit `"Wire active-connection control platforms"`.

### Task 14: README + docs

**Files:**
- Modify: `README.md`

- [ ] Document the active-connection opt-in (predictions + control), the new writable entities, the connectable-proxy requirement (Voice box, not Shelly), and the beta status. Commit `"Document UART active control"`.

---

## Self-review notes

- **Spec coverage:** framing (T1), all commands incl. resets/power/id/colour (T2), alarms (T11–12), ConnectionManager with disconnect handling + state broadcast (T3), predictions-as-consumer (T4), opt-in replacement (T5), ControlManager (T6), number/select/button/Connected entities (T7–10), wiring + docs (T13–14). All spec sections mapped.
- **Deferred within plan, by design:** per-sensor alarm control (defaults to core) and MeatNet-routed writes (direct-probe only) — both called out as follow-ups in the spec's non-goals.
- **CRC/frame** verified against reference (`0x29B1`, `cafeb9700502580a`) so no endianness guesswork remains.
