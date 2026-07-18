from __future__ import annotations

from .models import RiskEvent, RiskLevel, SensorFrame


def evaluate_risk(frame: SensorFrame) -> RiskEvent:
    """把道路、驾驶员和车辆信号融合为一个可解释的风险事件。"""

    road = frame.road
    driver = frame.driver
    vehicle = frame.vehicle
    evidence: list[str] = []

    if road.pedestrian_detected:
        evidence.append("前方行人")
    if road.lane_departure:
        evidence.append("车道偏离")
    if road.front_vehicle_risk != RiskLevel.LOW:
        evidence.append(f"前车风险:{road.front_vehicle_risk.value}")
    if driver.distracted:
        evidence.append("驾驶员注意力偏移")
    if driver.fatigue_level != RiskLevel.LOW:
        evidence.append(f"疲劳:{driver.fatigue_level.value}")
    if driver.eyes_closed_duration >= 1.5:
        evidence.append("持续闭眼")
    if vehicle and not vehicle.seatbelt_fastened:
        evidence.append("安全带未系")

    # P0复合风险：道路弱势目标与驾驶员分心同时出现。
    if road.pedestrian_detected and driver.distracted:
        return RiskEvent(
            event="pedestrian_and_distraction",
            level=RiskLevel.HIGH,
            timestamp=frame.timestamp,
            message="前方检测到行人且驾驶员注意力偏移",
            evidence=evidence,
        )

    if driver.eyes_closed_duration >= 1.5 or (
        road.lane_departure and driver.fatigue_level == RiskLevel.HIGH
    ):
        return RiskEvent(
            event="critical_driver_state",
            level=RiskLevel.HIGH,
            timestamp=frame.timestamp,
            message="驾驶员状态与道路风险形成高风险组合",
            evidence=evidence,
        )

    medium = (
        road.pedestrian_detected
        or road.lane_departure
        or driver.distracted
        or driver.fatigue_level == RiskLevel.MEDIUM
        or road.front_vehicle_risk == RiskLevel.MEDIUM
        or (vehicle is not None and not vehicle.seatbelt_fastened)
    )
    if medium:
        return RiskEvent(
            event="attention_required",
            level=RiskLevel.MEDIUM,
            timestamp=frame.timestamp,
            message="检测到需要关注的通勤风险",
            evidence=evidence,
        )

    return RiskEvent(
        event="normal_driving",
        level=RiskLevel.LOW,
        timestamp=frame.timestamp,
        message="当前通勤状态稳定",
        evidence=evidence,
    )

