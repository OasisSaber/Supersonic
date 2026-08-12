from unittest.mock import AsyncMock, Mock

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


def test_composed_app_keeps_platform_routes_truthfully_unavailable_without_database() -> None:
    app = create_app(settings=RuntimeSettings())

    with TestClient(app) as client:
        platform = client.post(
            "/api/platform/session/login",
            headers={"Origin": "http://127.0.0.1:5173"},
            json={"username": "operator", "password": "secret"},
        )
        health = client.get("/api/health")
        snapshot = client.get("/api/v1/snapshot")

    assert platform.status_code == 503
    assert platform.json()["error"]["code"] == "platform_unavailable"
    assert health.status_code == 200
    assert snapshot.status_code == 200


def test_database_engine_is_lazy_and_disposed_by_owning_app_lifespan(monkeypatch) -> None:
    engine = Mock()
    engine.dispose = AsyncMock()
    create_engine = Mock(return_value=engine)
    monkeypatch.setattr("app.main.create_database_engine", create_engine)
    monkeypatch.setattr("app.main.create_session_factory", Mock(return_value=Mock()))

    app = create_app(
        settings=RuntimeSettings(
            database_url="postgresql+psycopg://user:secret@db/supersonic"
        )
    )

    create_engine.assert_called_once()
    assert not engine.connect.called
    assert not engine.dispose.await_count
    with TestClient(app):
        pass
    engine.dispose.assert_awaited_once_with()


def test_cors_allows_gp05_and_configured_platform_origins() -> None:
    app = create_app(
        settings=RuntimeSettings(platform_ui_origin="https://platform.example.test")
    )

    with TestClient(app) as client:
        for origin in (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://platform.example.test",
        ):
            response = client.options(
                "/api/platform/session/login",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
            assert response.headers["access-control-allow-credentials"] == "true"
