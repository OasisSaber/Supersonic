from __future__ import annotations

import json
from pathlib import Path

from .models import SensorFrame, VehicleState

ROOT = Path(__file__).resolve().parents[3]
EVENTS_PATH = ROOT / "demo-data" / "mock" / "events.json"


def load_mock_frames() -> list[SensorFrame]:
    payload = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    return [SensorFrame.model_validate(item) for item in payload]


def vehicle_for_sequence(sequence: int) -> VehicleState:
    speed_curve = [32, 38, 44, 48, 51, 46, 40, 34]
    speed = speed_curve[sequence % len(speed_curve)]
    return VehicleState(
        speed=speed,
        battery=max(20, 82 - sequence * 0.15),
        range_km=max(80, 438 - sequence * 0.8),
        drive_mode="舒适" if sequence % 6 else "节能",
        battery_temperature=29 + (sequence % 4) * 0.6,
    )

