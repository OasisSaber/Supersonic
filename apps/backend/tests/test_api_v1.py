from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.cockpit_state import CockpitStateAuthority
from app.config import RuntimeSettings
from app.main import create_app


def command_payload(
    name: str,
    parameters: dict,
    *,
    endpoint: str = "control",
    source_id: str | None = None,
) -> dict:
    return {
        "protocolVersion": "gp05.v1",
        "messageId": str(uuid4()),
        "correlationId": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "source": {"kind": "endpoint", "id": source_id or endpoint},
        "kind": "command",
        "payload": {"name": name, "endpoint": endpoint, "parameters": parameters},
    }


def control_enabled_app():
    return create_app(
        CockpitStateAuthority(), settings=RuntimeSettings(control_enabled=True)
    )


async def test_snapshot_and_command_http_api() -> None:
    app = control_enabled_app()
    payload = command_payload("set_theme", {"theme": "day"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        initial = await client.get("/api/v1/snapshot")
        changed = await client.post("/api/v1/commands/control", json=payload)

    assert initial.status_code == 200
    assert initial.json()["revision"] == 0
    assert changed.status_code == 200
    assert changed.json()["correlationId"] == payload["correlationId"]
    assert changed.json()["payload"]["theme"] == "day"


async def test_command_rejection_has_stable_error_shape() -> None:
    app = control_enabled_app()
    payload = command_payload("set_theme", {"theme": "day"}, source_id="passenger")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/commands/control", json=payload)
        snapshot = await client.get("/api/v1/snapshot")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "source_mismatch"
    assert snapshot.json()["revision"] == 0


async def test_invalid_parameters_do_not_mutate_state() -> None:
    app = control_enabled_app()
    payload = command_payload("set_theme", {"theme": "purple"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/commands/control", json=payload)
        snapshot = await client.get("/api/v1/snapshot")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_parameters"
    assert snapshot.json()["revision"] == 0


async def test_cross_endpoint_spoofing_is_rejected_by_server_context() -> None:
    app = control_enabled_app()
    payload = command_payload("set_theme", {"theme": "day"}, endpoint="control")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/commands/cluster", json=payload)
        snapshot = await client.get("/api/v1/snapshot")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "endpoint_mismatch"
    assert snapshot.json()["revision"] == 0


async def test_control_commands_are_disabled_by_default() -> None:
    app = create_app(CockpitStateAuthority())
    payload = command_payload("set_theme", {"theme": "day"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/commands/control", json=payload)
        snapshot = await client.get("/api/v1/snapshot")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "control_disabled"
    assert snapshot.json()["revision"] == 0


async def test_control_status_reports_only_the_local_enable_boundary() -> None:
    disabled = create_app(CockpitStateAuthority())
    enabled = control_enabled_app()
    async with AsyncClient(transport=ASGITransport(app=disabled), base_url="http://test") as client:
        disabled_response = await client.get("/api/v1/control/status")
    async with AsyncClient(transport=ASGITransport(app=enabled), base_url="http://test") as client:
        enabled_response = await client.get("/api/v1/control/status")

    assert disabled_response.json() == {"controlEnabled": False}
    assert enabled_response.json() == {"controlEnabled": True}


async def test_unknown_endpoint_path_is_rejected() -> None:
    app = create_app(CockpitStateAuthority())
    payload = command_payload("set_theme", {"theme": "day"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/commands/not-an-endpoint", json=payload)

    assert response.status_code == 422


def test_websocket_starts_with_full_connected_snapshot() -> None:
    app = create_app(CockpitStateAuthority())

    with TestClient(app) as client:
        with client.websocket_connect("/ws/v1/cockpit?endpoint=cluster") as websocket:
            message = websocket.receive_json()

    assert message["kind"] == "snapshot"
    assert message["protocolVersion"] == "gp05.v1"
    assert message["payload"]["endpointConnectivity"]["cluster"]["status"] == "fresh"
    assert message["payload"]["revision"] == 1


def test_websocket_reconnect_gets_latest_full_snapshot() -> None:
    authority = CockpitStateAuthority()
    app = create_app(authority)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/v1/cockpit?endpoint=hud") as websocket:
            first = websocket.receive_json()
        with client.websocket_connect("/ws/v1/cockpit?endpoint=hud") as websocket:
            second = websocket.receive_json()

    assert second["payload"]["sessionId"] == first["payload"]["sessionId"]
    assert second["payload"]["revision"] > first["payload"]["revision"]
    assert second["payload"]["endpointConnectivity"]["hud"]["status"] == "fresh"


def test_websocket_receives_one_coherent_post_reset_snapshot() -> None:
    app = control_enabled_app()
    payload = command_payload("reset_session", {})
    with TestClient(app) as client:
        with client.websocket_connect("/ws/v1/cockpit?endpoint=cluster") as websocket:
            first = websocket.receive_json()
            response = client.post("/api/v1/commands/control", json=payload)
            second = websocket.receive_json()
            websocket.close()
            for _ in range(20):
                disconnected = client.get("/api/v1/snapshot")
                if disconnected.json()["endpointConnectivity"]["cluster"]["status"] == "offline":
                    break
            else:
                raise AssertionError("WebSocket disconnect cleanup did not complete")

    assert response.status_code == 200
    assert second["payload"]["sessionId"] != first["payload"]["sessionId"]
    assert second["payload"]["revision"] > first["payload"]["revision"]
    assert second["payload"]["endpointConnectivity"]["cluster"]["status"] == "fresh"
