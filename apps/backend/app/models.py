from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RoadState(BaseModel):
    pedestrian_detected: bool = False
    vehicle_count: int = Field(default=0, ge=0)
    lane_departure: bool = False
    front_vehicle_risk: RiskLevel = RiskLevel.LOW


class DriverState(BaseModel):
    fatigue_level: RiskLevel = RiskLevel.LOW
    distracted: bool = False
    eyes_closed_duration: float = Field(default=0.0, ge=0)
    yawning: bool = False


class VehicleState(BaseModel):
    speed: float = Field(default=0, ge=0, le=240)
    gear: str = "D"
    battery: float = Field(default=80, ge=0, le=100)
    range_km: float = Field(default=420, ge=0)
    drive_mode: str = "舒适"
    battery_temperature: float = 28
    seatbelt_fastened: bool = True


class SensorFrame(BaseModel):
    timestamp: float = Field(ge=0)
    road: RoadState
    driver: DriverState
    vehicle: VehicleState | None = None


class RiskEvent(BaseModel):
    event: str
    level: RiskLevel
    timestamp: float
    message: str
    evidence: list[str] = Field(default_factory=list)


class SimulationFrame(BaseModel):
    sequence: int
    vehicle: VehicleState
    sensor: SensorFrame
    risk: RiskEvent


class TripRecord(BaseModel):
    trip_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_seconds: float
    frames_processed: int
    highest_risk: RiskLevel
    events: list[RiskEvent]
    summary: str


class ReportRequest(BaseModel):
    trip: TripRecord


class ReportResponse(BaseModel):
    provider: str = "mock"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    risk_explanation: str
    trip_report: str
