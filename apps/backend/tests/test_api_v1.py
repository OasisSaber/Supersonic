from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.cockpit_state import CockpitStateAuthority
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


async def test_snapshot_and_command_http_api() -> None:
    app = create_app(CockpitStateAuthority())
    payload = command_payload("set_theme", {"theme": "day"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        initial = await client.get("/api/v1/snapshot")
        changed = await client.post("/api/v1/commands", json=payload)

    assert initial.status_code == 200
    assert initial.json()["revision"] == 0
    assert changed.status_code == 200
    assert changed.json()["correlationId"] == payload["correlationId"]
    assert changed.json()["payload"]["theme"] == "day"


async def test_command_rejection_has_stable_error_shape() -> None:
    app = create_app(CockpitStateAuthority())
    payload = command_payload("set_theme", {"theme": "day"}, source_id="passenger")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/commands", json=payload)
        snapshot = await client.get("/api/v1/snapshot")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "source_mismatch"
    assert snapshot.json()["revision"] == 0


async def test_invalid_parameters_do_not_mutate_state() -> None:
    app = create_app(CockpitStateAuthority())
    payload = command_payload("set_theme", {"theme": "purple"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/commands", json=payload)
        snapshot = await client.get("/api/v1/snapshot")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_parameters"
    assert snapshot.json()["revision"] == 0


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
