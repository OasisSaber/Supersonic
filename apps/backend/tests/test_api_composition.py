from fastapi.testclient import TestClient

from app.cockpit.service import CockpitService
from app.config import AppMode, RuntimeSettings
from app.main import create_app


def test_composed_app_exposes_health_and_cockpit_routes() -> None:
    app = create_app(
        authority=CockpitService(),
        settings=RuntimeSettings(
            app_mode=AppMode.MOCK,
            control_enabled=False,
        ),
    )

    with TestClient(app) as client:
        health = client.get("/api/health")
        snapshot = client.get("/api/v1/snapshot")
        control = client.get("/api/v1/control/status")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "mode": "mock"}
    assert snapshot.status_code == 200
    assert control.json() == {"controlEnabled": False}
