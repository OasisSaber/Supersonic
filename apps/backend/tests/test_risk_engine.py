from app.models import DriverState, RoadState, SensorFrame, VehicleState
from app.risk_engine import evaluate_risk


def test_pedestrian_and_distraction_is_high_risk() -> None:
    frame = SensorFrame(
        timestamp=125.6,
        road=RoadState(pedestrian_detected=True, vehicle_count=3),
        driver=DriverState(distracted=True, fatigue_level="medium"),
    )

    result = evaluate_risk(frame)

    assert result.event == "pedestrian_and_distraction"
    assert result.level == "high"
    assert "前方行人" in result.evidence
    assert "驾驶员注意力偏移" in result.evidence


def test_normal_frame_is_low_risk() -> None:
    frame = SensorFrame(timestamp=1.0, road=RoadState(), driver=DriverState())
    result = evaluate_risk(frame)
    assert result.level == "low"
    assert result.event == "normal_driving"


def test_high_front_vehicle_risk_alone_is_never_low() -> None:
    frame = SensorFrame(
        timestamp=2.0,
        road=RoadState(front_vehicle_risk="high"),
        driver=DriverState(),
    )

    result = evaluate_risk(frame)

    assert result.level == "medium"
    assert result.event == "attention_required"
    assert "前车风险:high" in result.evidence


def test_high_fatigue_alone_is_never_low() -> None:
    frame = SensorFrame(
        timestamp=3.0,
        road=RoadState(),
        driver=DriverState(fatigue_level="high"),
    )

    result = evaluate_risk(frame)

    assert result.level == "medium"
    assert result.event == "attention_required"
    assert "疲劳:high" in result.evidence


def test_eyes_closed_duration_boundary_at_1_5_seconds() -> None:
    at_threshold = SensorFrame(
        timestamp=4.0,
        road=RoadState(),
        driver=DriverState(eyes_closed_duration=1.5),
    )
    below_threshold = SensorFrame(
        timestamp=4.1,
        road=RoadState(),
        driver=DriverState(eyes_closed_duration=1.49),
    )

    assert evaluate_risk(at_threshold).level == "high"
    assert evaluate_risk(at_threshold).event == "critical_driver_state"
    assert evaluate_risk(below_threshold).level == "low"


def test_unfastened_seatbelt_is_medium_risk() -> None:
    frame = SensorFrame(
        timestamp=5.0,
        road=RoadState(),
        driver=DriverState(),
        vehicle=VehicleState(seatbelt_fastened=False),
    )

    result = evaluate_risk(frame)

    assert result.level == "medium"
    assert result.event == "attention_required"
    assert "安全带未系" in result.evidence

