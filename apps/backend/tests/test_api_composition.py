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
        client.cookies.set("supersonic_platform_session_dev", "raw-secret")
        admin = client.get("/api/platform/admin/users")
        audit = client.get("/api/platform/audit")
        mutation = client.post(
            "/api/platform/admin/users/user-1/role",
            headers={"Origin": "http://127.0.0.1:5173"},
            json={"role": "viewer"},
        )
        health = client.get("/api/health")
        snapshot = client.get("/api/v1/snapshot")

    assert platform.status_code == 503
    assert platform.json()["error"]["code"] == "platform_unavailable"
    for response in (admin, audit, mutation):
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["error"]["code"] == "platform_unavailable"
    assert health.status_code == 200
    assert snapshot.status_code == 200


def test_database_composition_reuses_readiness_uow_and_registry_callback(
    monkeypatch,
) -> None:
    database_url = "postgresql+psycopg://user:secret@db/supersonic"
    engine = Mock()
    engine.dispose = AsyncMock()
    session_factory = Mock(name="session_factory")
    readiness = Mock(name="readiness")
    registry = Mock(name="websocket_registry")
    session_service = Mock(name="session_service")
    admin_service = Mock(name="admin_service")
    audit_service = Mock(name="audit_service")
    create_engine = Mock(return_value=engine)
    create_session_factory = Mock(return_value=session_factory)
    create_readiness = Mock(return_value=readiness)
    create_registry = Mock(return_value=registry)
    create_session_service = Mock(return_value=session_service)
    create_admin_service = Mock(return_value=admin_service)
    create_audit_service = Mock(return_value=audit_service)
    create_uow = Mock(return_value=Mock(name="unit_of_work"))

    monkeypatch.setattr("app.main.create_database_engine", create_engine)
    monkeypatch.setattr("app.main.create_session_factory", create_session_factory)
    monkeypatch.setattr("app.main.SqlAlchemyPlatformReadiness", create_readiness)
    monkeypatch.setattr("app.main.WebSocketSessionRegistry", create_registry)
    monkeypatch.setattr("app.main.SessionService", create_session_service)
    monkeypatch.setattr("app.main.UserAdminService", create_admin_service)
    monkeypatch.setattr("app.main.AuditQueryService", create_audit_service)
    monkeypatch.setattr("app.main.SqlAlchemyPlatformUnitOfWork", create_uow)

    app = create_app(settings=RuntimeSettings(database_url=database_url))

    create_engine.assert_called_once_with(database_url)
    create_session_factory.assert_called_once_with(engine)
    create_readiness.assert_called_once_with(database_url, engine=engine)
    create_registry.assert_called_once_with()

    session_options = create_session_service.call_args.kwargs
    admin_options = create_admin_service.call_args.kwargs
    audit_options = create_audit_service.call_args.kwargs
    assert session_options["readiness"] is readiness
    assert admin_options["readiness"] is readiness
    assert audit_options["readiness"] is readiness
    assert session_options["uow_factory"] is admin_options["uow_factory"]
    assert admin_options["uow_factory"] is audit_options["uow_factory"]
    assert session_options["on_revoke"] is registry.close_all
    assert admin_options["on_revoke"] is registry.close_all
    assert admin_options["uow_factory"]() is create_uow.return_value
    create_uow.assert_called_once_with(session_factory)

    paths = set(app.openapi()["paths"])
    assert {
        "/api/platform/admin/users",
        "/api/platform/admin/users/{user_id}/sessions",
        "/api/platform/admin/users/{user_id}/role",
        "/api/platform/admin/users/{user_id}/disabled",
        "/api/platform/admin/sessions/{session_id}/revoke",
        "/api/platform/audit",
    } <= paths


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


def test_cors_allows_only_configured_origins_contract_methods_and_headers() -> None:
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
            assert response.headers["access-control-allow-methods"] == "GET, POST"
            assert response.headers["access-control-allow-headers"] == "Content-Type"

        for method, requested_headers in (
            ("PUT", "content-type"),
            ("POST", "accept"),
            ("POST", "accept-language"),
            ("POST", "content-language"),
            ("POST", "x-uncontracted-header"),
        ):
            response = client.options(
                "/api/platform/session/login",
                headers={
                    "Origin": "https://platform.example.test",
                    "Access-Control-Request-Method": method,
                    "Access-Control-Request-Headers": requested_headers,
                },
            )
            assert response.status_code == 400

        response = client.options(
            "/api/platform/session/login",
            headers={
                "Origin": "https://untrusted.example.test",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 400
