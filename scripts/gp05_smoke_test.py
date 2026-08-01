"""Real-process smoke test for the gp05.v1 cockpit runtime chain."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import websockets


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = ("cluster", "hud", "center", "passenger")
PROCESS_TIMEOUT_SECONDS = 30


def reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def validate_snapshot(message: dict[str, Any]) -> dict[str, Any]:
    assert message["protocolVersion"] == "gp05.v1"
    assert message["kind"] == "snapshot"
    assert message["source"] == {
        "kind": "service",
        "id": "cockpit-state-authority",
    }
    assert isinstance(message["messageId"], str)
    assert isinstance(message["correlationId"], str)
    payload = message["payload"]
    assert isinstance(payload["sessionId"], str) and payload["sessionId"]
    assert isinstance(payload["revision"], int) and payload["revision"] >= 0
    assert set(ENDPOINTS).issubset(payload["endpointConnectivity"])
    return payload


async def receive_until(
    websocket: Any,
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    async with asyncio.timeout(5):
        while True:
            payload = validate_snapshot(json.loads(await websocket.recv()))
            if predicate(payload):
                return payload


async def receive_all(
    sockets: dict[str, Any],
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, dict[str, Any]]:
    payloads = await asyncio.gather(
        *(receive_until(websocket, predicate) for websocket in sockets.values())
    )
    return dict(zip(sockets, payloads, strict=True))


def all_clients_fresh(payload: dict[str, Any]) -> bool:
    return all(
        payload["endpointConnectivity"][endpoint]["status"] == "fresh"
        for endpoint in ENDPOINTS
    )


def assert_converged(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    snapshots = list(payloads.values())
    expected = snapshots[0]
    assert all(snapshot == expected for snapshot in snapshots[1:])
    return expected


def command_payload(endpoint: str, name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocolVersion": "gp05.v1",
        "messageId": str(uuid4()),
        "correlationId": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "source": {"kind": "endpoint", "id": endpoint},
        "kind": "command",
        "payload": {
            "name": name,
            "endpoint": endpoint,
            "parameters": parameters,
        },
    }


async def wait_for_server(client: httpx.AsyncClient, process: subprocess.Popen[bytes]) -> None:
    async with asyncio.timeout(10):
        while True:
            if process.poll() is not None:
                raise AssertionError(f"Uvicorn exited during startup with code {process.returncode}")
            try:
                response = await client.get("/api/health")
                if response.status_code == 200:
                    assert response.json() == {"status": "ok", "mode": "mock"}
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.1)


async def wait_for_endpoint_offline(client: httpx.AsyncClient, endpoint: str) -> None:
    async with asyncio.timeout(5):
        while True:
            snapshot = (await client.get("/api/v1/snapshot")).raise_for_status().json()
            if snapshot["endpointConnectivity"][endpoint]["status"] == "offline":
                return
            await asyncio.sleep(0.05)


async def exercise_runtime(port: int, process: subprocess.Popen[bytes]) -> dict[str, Any]:
    base_url = f"http://127.0.0.1:{port}"
    websocket_url = f"ws://127.0.0.1:{port}/ws/v1/cockpit"
    sockets: dict[str, Any] = {}
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
        await wait_for_server(client, process)
        try:
            connections = await asyncio.gather(
                *(
                    websockets.connect(
                        f"{websocket_url}?endpoint={endpoint}",
                        open_timeout=5,
                        close_timeout=2,
                    )
                    for endpoint in ENDPOINTS
                )
            )
            sockets.update(zip(ENDPOINTS, connections, strict=True))

            connected = assert_converged(
                await receive_all(sockets, all_clients_fresh)
            )
            initial_session = connected["sessionId"]

            destination = "GP05 Smoke Destination"
            center_response = await client.post(
                "/api/v1/commands/center",
                json=command_payload(
                    "center",
                    "select_destination",
                    {"destinationName": destination},
                ),
            )
            center_response.raise_for_status()
            center_revision = center_response.json()["payload"]["revision"]
            navigated = assert_converged(
                await receive_all(
                    sockets,
                    lambda payload: payload["revision"] >= center_revision,
                )
            )
            assert navigated["navigation"]["destinationName"] == destination

            driver_state = {
                key: navigated[key]
                for key in ("vehicle", "navigation", "systemMode", "theme", "risks")
            }
            suggestion = "Stop for coffee"
            passenger_response = await client.post(
                "/api/v1/commands/passenger",
                json=command_payload(
                    "passenger",
                    "submit_trip_suggestion",
                    {"suggestion": suggestion},
                ),
            )
            passenger_response.raise_for_status()
            passenger_revision = passenger_response.json()["payload"]["revision"]
            suggested = assert_converged(
                await receive_all(
                    sockets,
                    lambda payload: payload["revision"] >= passenger_revision,
                )
            )
            assert suggested["passenger"]["tripSuggestions"][0] == suggestion
            assert {
                key: suggested[key]
                for key in ("vehicle", "navigation", "systemMode", "theme", "risks")
            } == driver_state

            forbidden_revision = suggested["revision"]
            forbidden = await client.post(
                "/api/v1/commands/passenger",
                json=command_payload("passenger", "set_theme", {"theme": "day"}),
            )
            assert forbidden.status_code == 403
            assert forbidden.json()["error"]["code"] == "command_forbidden"
            unchanged = (await client.get("/api/v1/snapshot")).raise_for_status().json()
            assert unchanged["revision"] == forbidden_revision

            reset_response = await client.post(
                "/api/v1/commands/control",
                json=command_payload("control", "reset_session", {}),
            )
            reset_response.raise_for_status()
            reset_revision = reset_response.json()["payload"]["revision"]
            reset = assert_converged(
                await receive_all(
                    sockets,
                    lambda payload: payload["revision"] >= reset_revision
                    and payload["sessionId"] != initial_session
                    and all_clients_fresh(payload),
                )
            )

            await sockets.pop("hud").close()
            await wait_for_endpoint_offline(client, "hud")
            sockets["hud"] = await websockets.connect(
                f"{websocket_url}?endpoint=hud",
                open_timeout=5,
                close_timeout=2,
            )
            async with asyncio.timeout(5):
                reconnected = validate_snapshot(
                    json.loads(await sockets["hud"].recv())
                )
            assert reconnected["sessionId"] == reset["sessionId"]
            assert reconnected["revision"] > reset["revision"]
            assert all_clients_fresh(reconnected)
            assert reconnected["passenger"] == reset["passenger"]
            assert reconnected["navigation"] == reset["navigation"]

            return {
                "protocol": "gp05.v1",
                "clients": list(ENDPOINTS),
                "initialSession": initial_session,
                "resetSession": reset["sessionId"],
                "finalRevision": reconnected["revision"],
                "forbiddenCommand": "command_forbidden",
            }
        finally:
            await asyncio.gather(
                *(websocket.close() for websocket in sockets.values()),
                return_exceptions=True,
            )


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


async def main() -> None:
    port = reserve_local_port()
    environment = os.environ.copy()
    environment["CONTROL_ENABLED"] = "true"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "apps/backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        async with asyncio.timeout(PROCESS_TIMEOUT_SECONDS):
            result = await exercise_runtime(port, process)
    finally:
        stop_process(process)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
