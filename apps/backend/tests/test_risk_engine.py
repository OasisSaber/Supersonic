from app.models import DriverState, RoadState, SensorFrame
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

