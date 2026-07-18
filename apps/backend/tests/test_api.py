from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_and_demo_trip() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/api/health")
        trip = await client.get("/api/trips/demo")

    assert health.status_code == 200
    assert health.json()["mode"] == "mock"
    assert trip.status_code == 200
    assert trip.json()["highest_risk"] == "high"


async def test_mock_report_is_labeled() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        trip = (await client.get("/api/trips/demo")).json()
        response = await client.post("/api/report/generate", json={"trip": trip})

    assert response.status_code == 200
    assert response.json()["provider"] == "mock"
    assert "不构成真实驾驶" in response.json()["trip_report"]
