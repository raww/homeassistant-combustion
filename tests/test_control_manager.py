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
