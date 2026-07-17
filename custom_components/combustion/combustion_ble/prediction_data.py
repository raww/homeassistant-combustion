"""Parser for Combustion Predictive Probe prediction data.

Prediction data is only available over a GATT connection (the Probe Status
characteristic), not in advertisements. Bit-packing follows Combustion's
Android library (PredictionStatus.fromRawData); see
https://github.com/combustion-inc/combustion-android-ble.
"""
from __future__ import annotations

from typing import NamedTuple

# Probe Status characteristic layout (bytes):
#   [0:8]   Log range (2x uint32)
#   [8:21]  Current raw temperature data (13)
#   [21]    Mode/ID
#   [22]    Battery status & virtual sensors
#   [23:30] Prediction status (7)   <- parsed here
#   ... food safe, overheating, prefs, alarm arrays follow
PREDICTION_STATUS_OFFSET = 23
PREDICTION_STATUS_SIZE = 7

PREDICTION_STATES = [
    'not_inserted', 'inserted', 'warming', 'predicting', 'removal_done',
    'reserved5', 'reserved6', 'reserved7', 'reserved8', 'reserved9',
    'unknown10', 'unknown11', 'unknown12', 'unknown13', 'unknown14', 'unknown15',
]
PREDICTION_MODES = ['none', 'time_to_removal', 'removal_and_resting', 'reserved']
PREDICTION_TYPES = ['none', 'removal', 'resting', 'reserved']

# A prediction value at or above this is the sentinel for "no prediction".
PREDICTION_MAX_SECONDS = 60 * 60 * 6  # 6 hours; longer readings are treated as absent


class PredictionData(NamedTuple):
    """Decoded prediction status for a predictive probe."""

    state: str
    mode: str
    type: str
    setpoint_c: float | None
    heat_start_c: float | None
    seconds_remaining: int | None
    estimated_core_c: float | None

    @property
    def is_predicting(self) -> bool:
        """Whether the probe is actively producing a time prediction."""
        return self.state == 'predicting' and self.seconds_remaining is not None

    @staticmethod
    def from_status_characteristic(data: bytes) -> PredictionData | None:
        """Parse prediction from a full Probe Status characteristic payload."""
        end = PREDICTION_STATUS_OFFSET + PREDICTION_STATUS_SIZE
        if data is None or len(data) < end:
            return None
        return PredictionData.from_prediction_status(data[PREDICTION_STATUS_OFFSET:end])

    @staticmethod
    def from_prediction_status(d: bytes) -> PredictionData | None:
        """Parse the 7-byte prediction status field."""
        if d is None or len(d) < PREDICTION_STATUS_SIZE:
            return None

        state = PREDICTION_STATES[d[0] & 0x0F]
        mode = PREDICTION_MODES[(d[0] >> 4) & 0x03]
        ptype = PREDICTION_TYPES[(d[0] >> 6) & 0x03]

        raw_setpoint = d[1] | ((d[2] & 0x03) << 8)
        raw_heatstart = ((d[2] & 0xFC) >> 2) | ((d[3] & 0x0F) << 6)
        raw_seconds = ((d[3] & 0xF0) >> 4) | (d[4] << 4) | ((d[5] & 0x1F) << 12)
        raw_core = ((d[5] & 0xE0) >> 5) | (d[6] << 3)

        # 0 is a valid "ready now" reading (the reference SDKs do not exclude it);
        # only cap absurdly long values, treating them as no prediction.
        seconds = raw_seconds if 0 <= raw_seconds <= PREDICTION_MAX_SECONDS else None

        return PredictionData(
            state=state,
            mode=mode,
            type=ptype,
            setpoint_c=round(raw_setpoint * 0.1, 1) if raw_setpoint else None,
            heat_start_c=round(raw_heatstart * 0.1, 1) if raw_heatstart else None,
            seconds_remaining=seconds,
            estimated_core_c=round(raw_core * 0.1 - 20.0, 1) if raw_core else None,
        )
