from __future__ import annotations

from .models import ReportResponse, RiskLevel, TripRecord


def generate_mock_report(trip: TripRecord) -> ReportResponse:
    """离线Mock报告：只根据结构化事件生成，不虚构传感器事实。"""

    high_count = sum(event.level == RiskLevel.HIGH for event in trip.events)
    medium_count = sum(event.level == RiskLevel.MEDIUM for event in trip.events)
    notable = [event.message for event in trip.events if event.level != RiskLevel.LOW]
    explanation = (
        "本次最高风险来自道路环境与驾驶员状态的组合判断。"
        + (f"关键证据：{'；'.join(notable[:3])}。" if notable else "未记录显著风险证据。")
    )
    report = (
        f"本次模拟行程持续 {trip.duration_seconds:.0f} 秒，"
        f"共处理 {trip.frames_processed} 个事件帧。"
        f"记录高风险事件 {high_count} 次、中风险事件 {medium_count} 次。"
        "建议在真实用户测试前继续校准风险阈值与警告节奏。本报告由Mock模式生成，"
        "不构成真实驾驶或安全建议。"
    )
    return ReportResponse(risk_explanation=explanation, trip_report=report)
