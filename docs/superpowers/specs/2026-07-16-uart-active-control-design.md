# UART Active Control — Design

**Status:** approved, pre-implementation
**Date:** 2026-07-16
**Ships as:** next `-beta` (behind the active-connection opt-in)

## Goal

Let Home Assistant *write* settings to Combustion probes and the gauge over the
BLE UART service — target/removal temperature, prediction mode, high/low alarms,
identity (probe ID + colour), power mode, and the reset commands — not just read
advertisements and prediction status.

This requires an **active (connectable)** BLE path (local adapter or an ESPHome
active proxy such as the kitchen Voice box). Passive proxies (Shelly) cannot do
it. All of it stays opt-in and off by default.

## Non-goals

- No MeatNet command routing in this cut: writes go direct-to-probe only, the
  same connection model the prediction reader already uses (`payload[0] == 0x01`
  direct probe advertisements). Routing writes through a Booster/Display by
  serial is a later change.
- No auto-retry of writes. A command either lands on a live link or fails loudly.

## Architecture

Connection ownership moves **out** of `PredictionManager` into a new
`ConnectionManager`. Both prediction-reading and control become *consumers* of
the shared connection — control never borrows a client that another object
privately owns.

```
                    ┌──────────────────────┐
                    │   ConnectionManager   │  owns per-probe BleakClient
                    │  (connection_manager) │  lifecycle + backoff reconnect
                    └──────────────────────┘
                     ▲ subscribe         ▲ async_send_command
          ┌──────────┘                   └──────────┐
   ┌───────────────┐                        ┌───────────────┐
   │ PredictionMgr │  notify: Probe Status  │ ControlManager │  write: UART RX
   │  (consumer)   │                        │  (consumer)    │
   └───────────────┘                        └───────────────┘
```

### `connection_manager.py` — `ConnectionManager`

Owns all BLE connection code (moved from `PredictionManager`):

- Registers the `connectable=True` advertisement callback. On a connectable
  direct-probe advert, ensures one `_maintain_connection(serial)` background
  task exists.
- `_maintain_connection(serial)`: persistent connect loop with exponential
  backoff (`RECONNECT_MIN_SECONDS=5` → `RECONNECT_MAX_SECONDS=300`), reset to min
  on a successful connect. Holds `self._clients: dict[str, BleakClient]`.
- **Notify registry:** `subscribe(char_uuid, handler)` records consumer
  subscriptions. On *every* (re)connect the manager calls `start_notify` for
  each subscribed char, so consumers never re-subscribe after a drop.
- **`async_send_command(serial, frame: bytes) -> Response`:** writes `frame` to
  the UART RX characteristic on the live client and returns the parsed response.
  - If no live client but a known address exists, it kicks the maintain loop to
    attempt an immediate connect, waits briefly, then writes.
  - If still not connected, raises `HomeAssistantError("<serial> is not
    connected")`. No queuing of stale commands.
- **Connection-state broadcast:** emits a state-change notification when a probe
  connects/disconnects (new — the current code only broadcasts data updates).
  Drives entity `available` and the "Connected" binary_sensor.
- `is_connected(serial) -> bool`.
- Clean unload: cancel all maintain tasks, disconnect all clients (preserved).

### Disconnect handling (explicit)

Disconnects are the normal case (probes sleep / go out of range / the phone app
takes the single connection slot), so:

1. **Reconnect** is automatic via the maintain loop + `disconnected_callback`.
2. **Notify re-subscription** is automatic on each reconnect — predictions
   self-heal.
3. **Writes while disconnected** fail with `HomeAssistantError` (after one
   connect attempt), surfaced by HA as a failed service call — never a silent
   no-op.
4. **Entity availability** tracks connection state via the broadcast.
5. **Mid-write disconnect**: bleak raises → caught → error surfaced → loop
   reconnects. Not auto-retried.
6. **Unload** cancels tasks and disconnects.

### `PredictionManager` (refactor)

Shrinks to a pure consumer: `subscribe(PROBE_STATUS_CHAR, handler)`, parse
`PredictionData`. All `bleak` / `establish_connection` / backoff code leaves it.
Existing prediction sensors and tests stay green through the move.

### `combustion_ble/uart.py` — framing (pure, no BLE)

Frame per `probe_ble_specification.rst`:

- Request: `CA FE` + CRC(2) + `msg_type`(1) + `len`(1) + payload.
- Response: `CA FE` + CRC(2) + `msg_type`(1) + `success`(1) + `len`(1) + payload.
- CRC-16-CCITT (poly `0x1021`, init `0xFFFF`) over `msg_type + len + payload`.
  **CRC field byte order is pinned by a test vector cross-checked against the
  combustion-ios/android source** (spec does not state endianness).

API:

- `crc16_ccitt(data: bytes) -> int`
- `build_request(msg_type: int, payload: bytes) -> bytes`
- `parse_response(data: bytes) -> Response`  (`msg_type`, `success: bool`, `payload`)
- Command builders (own their bit-packing), returning framed bytes:
  - `set_prediction(setpoint_c: float, mode: PredictionMode)` — 10-bit setpoint
    in 0.1 °C (0–1023) + 2-bit mode, packed into uint16. (`0x05`)
  - `set_high_low_alarm(...)` — probe (`0x0B`)
  - `silence_alarms()` (`0x0C`)
  - `set_probe_id(n: int)` (`0x01`), `set_probe_colour(n: int)` (`0x02`)
  - `set_power_mode(m)` (`0x09`)
  - `reset_thermometer()` (`0x0A`), `reset_food_safe()` (`0x08`)
  - gauge: `set_gauge_high_low_alarm(...)` (`0x61`)

### `control_manager.py` — `ControlManager`

No BLE code. Builds a command via `uart.py`, calls
`ConnectionManager.async_send_command`, checks the response `success` bit, raises
`HomeAssistantError` on failure. Exposes typed methods the entities call
(`async_set_target(serial, temp_c)`, etc.).

## HA entity surface

New platforms. All `EntityCategory.CONFIG`, present only when active-connection
is enabled, `available` only when the probe is connected.

| Platform | Entities |
|---|---|
| `number` (new)  | Target temp; High-alarm temp; Low-alarm temp; Probe ID |
| `select` (new)  | Prediction mode; Probe colour; Power mode |
| `button` (new)  | Silence alarms; **Reset thermometer**; **Reset food safe** |
| `binary_sensor` | **Connected** (diagnostic, per probe) — from connection-state broadcast |

**Footgun guard:** Reset thermometer / Reset food safe buttons are
`entity_registry_enabled_default=False`. HA buttons have no native confirm, so
requiring the user to enable the entity first is the deliberate-action gate.

Gauge gets Target/alarm equivalents only where the gauge UART supports them
(High/Low alarm `0x61`); no prediction/ID/colour on the gauge.

## Opt-in

`CONF_ENABLE_PREDICTIONS` is **replaced outright** by
`CONF_ENABLE_ACTIVE_CONNECTION` (label: "Active connection (predictions +
control)"). No alias, no migration — single-user fork; the box is re-ticked once.
Everything (predictions + control) lives behind this one toggle, off by default.

## Testing (no hardware required)

- Framing/CRC against fixed vectors (cross-checked vs. reference lib).
- Per-command bit-packing round-trips (setpoint/mode, alarm fields, IDs).
- `ConnectionManager` with a fake bleak client: connect → `start_notify` fires
  for subscriptions; disconnect → reconnect + re-subscribe; `send_command` while
  disconnected raises; connect-then-write path; connection-state broadcast.
- Entity wiring with a mock `ControlManager`: setting number/select emits the
  right frame; entities go unavailable on disconnect.
- Existing prediction tests remain green after the ownership move.

## Files

- **new** `custom_components/combustion/connection_manager.py`
- **new** `custom_components/combustion/control_manager.py`
- **new** `custom_components/combustion/combustion_ble/uart.py`
- **new** `custom_components/combustion/number.py`
- **new** `custom_components/combustion/select.py`
- **new** `custom_components/combustion/button.py`
- **edit** `prediction_manager.py` (drop connection code → consumer)
- **edit** `binary_sensor.py` (add Connected diagnostic)
- **edit** `__init__.py` (wire ConnectionManager/ControlManager, new platforms)
- **edit** `config_flow.py` / `const.py` (replace the opt-in flag)
- **edit** `manifest.json` platforms, README
- **new** tests: `test_uart.py`, `test_connection_manager.py`, control/entity tests

## Risks / unknowns to resolve in implementation

- CRC endianness in the frame — resolve with a reference test vector before
  wiring any real write.
- Whether the probe requires bonding/pairing to accept writes, or rejects writes
  while the phone app holds the connection — can only be confirmed on hardware;
  the design surfaces failures cleanly so this is diagnosable.
- Gauge UART command availability beyond `0x61` — confirm against
  `gauge_ble_specification.rst` during implementation.
