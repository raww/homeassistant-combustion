"""Tests for ControlManager -> ConnectionManager wiring."""
import pytest
from combustion.combustion_ble.uart import (
    PredictionMode,
    set_prediction,
    set_probe_high_low_alarm,
)
from combustion.control_manager import ControlManager
from homeassistant.exceptions import HomeAssistantError


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
async def test_set_mode_reuses_last_target():
    """Changing mode alone re-sends Set Prediction with the remembered target temp."""
    conn = _FakeConn()
    mgr = ControlManager(conn)
    await mgr.async_set_target("S1", 60.0, PredictionMode.TIME_TO_REMOVAL)
    await mgr.async_set_mode("S1", PredictionMode.REMOVAL_AND_RESTING)
    assert conn.sent[1][0] == "S1"
    assert conn.sent[1][1].hex() == set_prediction(60.0, PredictionMode.REMOVAL_AND_RESTING).hex()


@pytest.mark.asyncio
async def test_silence_sends_silence_frame():
    """Silence sends the 0x0C frame."""
    conn = _FakeConn()
    mgr = ControlManager(conn)
    await mgr.async_silence("S1")
    assert conn.sent[0][1].hex() == "cafe62580c00"


@pytest.mark.asyncio
async def test_set_high_alarm_sends_command():
    """Setting the high alarm sends a combined high/low alarm frame for the core sensor."""
    conn = _FakeConn()
    mgr = ControlManager(conn)
    await mgr.async_set_high_alarm("S1", 95.0)
    assert conn.sent[-1][0] == "S1"
    assert conn.sent[-1][1] == set_probe_high_low_alarm(8, True, 95.0, False, 0.0)


@pytest.mark.asyncio
async def test_set_low_then_high_enables_both():
    """Setting low then high remembers both and sends a frame with both enabled."""
    conn = _FakeConn()
    mgr = ControlManager(conn)
    await mgr.async_set_low_alarm("S1", 40.0)
    await mgr.async_set_high_alarm("S1", 95.0)
    assert conn.sent[-1][1] == set_probe_high_low_alarm(8, True, 95.0, True, 40.0)


@pytest.mark.asyncio
async def test_set_mode_without_target_raises():
    """Changing mode with no remembered target raises instead of sending a fabricated 0.0°C target."""
    conn = _FakeConn()
    mgr = ControlManager(conn)
    with pytest.raises(HomeAssistantError):
        await mgr.async_set_mode("S1", PredictionMode.REMOVAL_AND_RESTING)
    assert conn.sent == []


@pytest.mark.asyncio
async def test_remember_alarms_then_set_one_preserves_other():
    """Seeding remembered alarms (e.g. on restore) then setting one preserves the other."""
    conn = _FakeConn()
    mgr = ControlManager(conn)
    mgr.remember_high_alarm("S1", 95.0)
    mgr.remember_low_alarm("S1", 40.0)
    await mgr.async_set_high_alarm("S1", 100.0)
    assert conn.sent[-1][0] == "S1"
    assert conn.sent[-1][1] == set_probe_high_low_alarm(8, True, 100.0, True, 40.0)
