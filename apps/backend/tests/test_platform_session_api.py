from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.platform_session_router import PlatformUnavailable, create_platform_session_router
from app.config import PlatformAccessProfile, RuntimeSettings, platform_cookie_settings
from app.platform.models import Principal, Role
from app.platform.persistence import DatabaseUnavailable, MigrationRequired
from app.platform.sessions import (
    AuditPersistenceFailure,
    CredentialStoreInvalid,
    InvalidCredentials,
    InvalidSession,
    IssuedSession,
    LoginThrottled,
    SessionIdentity,
)

NOW = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)
ORIGIN = "http://127.0.0.1:5173"


@dataclass
class FakeSessionService:
    login_result: IssuedSession | Exception | None = None
    logout_result: bool | Exception = True
    resolve_result: SessionIdentity | Exception | None = None

    def __post_init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def login(self, username: str, password: str, remote_client_key: str) -> IssuedSession:
        self.calls.append(("login", username, password, remote_client_key))
        if isinstance(self.login_result, Exception):
            raise self.login_result
        assert self.login_result is not None
        return self.login_result

    async def logout(self, raw_secret: str) -> bool:
        self.calls.append(("logout", raw_secret))
        if isinstance(self.logout_result, Exception):
            raise self.logout_result
        return self.logout_result

    async def resolve(self, raw_secret: str) -> SessionIdentity:
        self.calls.append(("resolve", raw_secret))
        if isinstance(self.resolve_result, Exception):
            raise self.resolve_result
        assert self.resolve_result is not None
        return self.resolve_result


def issued() -> IssuedSession:
    return IssuedSession(
        token="raw-session-secret",
        platform_session_id="session-1",
        user_id="user-1",
        display_name="Alice",
        role=Role.OPERATOR,
        expires_at=NOW,
    )


def identity() -> SessionIdentity:
    return SessionIdentity(
        principal=Principal("user-current", Role.ADMIN, "session-current"),
        display_name="Current Alice",
        expires_at=NOW,
    )


def client_for(
    service: FakeSessionService, profile: PlatformAccessProfile = PlatformAccessProfile.LOOPBACK
) -> TestClient:
    settings = RuntimeSettings(
        platform_ui_origin=(ORIGIN if profile is PlatformAccessProfile.LOOPBACK else "https://ui.test"),
        platform_access_profile=profile,
        platform_cookie=platform_cookie_settings(profile),
    )
    app = FastAPI()
    app.include_router(create_platform_session_router(service, settings))
    return TestClient(app, client=("198.51.100.8", 54321))


def test_login_returns_only_identity_metadata_and_sets_loopback_cookie() -> None:
    service = FakeSessionService(login_result=issued())
    with client_for(service) as client:
        response = client.post(
            "/api/platform/session/login",
            headers={"Origin": ORIGIN},
            json={"username": "Alice", "password": "correct"},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "userId": "user-1",
        "displayName": "Alice",
        "role": "operator",
        "platformSessionId": "session-1",
        "expiresAt": "2026-08-12T08:00:00Z",
    }
    assert service.calls == [("login", "Alice", "correct", "198.51.100.8")]
    cookie = response.headers["set-cookie"]
    assert "supersonic_platform_session_dev=raw-session-secret" in cookie
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert "Secure" not in cookie and "Domain=" not in cookie


def test_https_profile_uses_secure_host_cookie() -> None:
    service = FakeSessionService(login_result=issued())
    with client_for(service, PlatformAccessProfile.HTTPS) as client:
        response = client.post(
            "/api/platform/session/login",
            headers={"Origin": "https://ui.test"},
            json={"username": "Alice", "password": "correct"},
        )
    cookie = response.headers["set-cookie"]
    assert "__Host-supersonic_platform_session=raw-session-secret" in cookie
    assert "Secure" in cookie and "HttpOnly" in cookie and "Domain=" not in cookie


@pytest.mark.parametrize("origin", [None, "null", ORIGIN + ".evil", ORIGIN + "/path"])
@pytest.mark.parametrize("path", ["login", "logout"])
def test_mutations_require_exact_origin(origin: str | None, path: str) -> None:
    service = FakeSessionService(login_result=issued())
    headers = {} if origin is None else {"Origin": origin}
    kwargs = {"json": {"username": "Alice", "password": "correct"}} if path == "login" else {}
    with client_for(service) as client:
        response = client.post(f"/api/platform/session/{path}", headers=headers, **kwargs)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": {"code": "origin_forbidden", "message": "Request origin is not allowed."}
    }
    assert service.calls == []


def test_logout_clears_cookie_only_after_service_success() -> None:
    service = FakeSessionService()
    with client_for(service) as client:
        client.cookies.set("supersonic_platform_session_dev", "raw-session-secret")
        response = client.post("/api/platform/session/logout", headers={"Origin": ORIGIN})
    assert response.status_code == 200
    assert response.json() == {"loggedOut": True}
    assert service.calls == [("logout", "raw-session-secret")]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"


def test_logout_failure_does_not_clear_cookie() -> None:
    service = FakeSessionService(logout_result=AuditPersistenceFailure())
    with client_for(service) as client:
        client.cookies.set("supersonic_platform_session_dev", "raw-session-secret")
        response = client.post("/api/platform/session/logout", headers={"Origin": ORIGIN})
    assert response.status_code == 503
    assert "set-cookie" not in response.headers


def test_me_resolves_cookie_and_returns_current_server_facts() -> None:
    service = FakeSessionService(resolve_result=identity())
    with client_for(service) as client:
        client.cookies.set("supersonic_platform_session_dev", "raw-session-secret")
        response = client.get("/api/platform/session/me")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "userId": "user-current",
        "displayName": "Current Alice",
        "role": "admin",
        "platformSessionId": "session-current",
        "expiresAt": "2026-08-12T08:00:00Z",
    }
    assert service.calls == [("resolve", "raw-session-secret")]


def test_missing_cookie_is_session_required_without_service_call() -> None:
    service = FakeSessionService()
    with client_for(service) as client:
        response = client.get("/api/platform/session/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_required"
    assert response.headers["cache-control"] == "no-store"
    assert service.calls == []


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (InvalidCredentials(), 401, "invalid_credentials"),
        (InvalidSession(), 401, "session_invalid"),
        (DatabaseUnavailable(), 503, "database_unavailable"),
        (MigrationRequired(), 503, "migration_required"),
        (PlatformUnavailable(), 503, "platform_unavailable"),
        (CredentialStoreInvalid(), 503, "credential_store_invalid"),
        (AuditPersistenceFailure(), 503, "audit_persistence_failure"),
    ],
)
def test_typed_failures_have_stable_sanitized_envelopes(
    error: Exception, status: int, code: str
) -> None:
    service = FakeSessionService(login_result=error)
    with client_for(service) as client:
        response = client.post(
            "/api/platform/session/login",
            headers={"Origin": ORIGIN},
            json={"username": "Alice", "password": "correct"},
        )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    body = response.text.lower()
    assert all(secret not in body for secret in ("correct", "postgresql://", "traceback", "digest"))


def test_throttling_has_retry_after() -> None:
    service = FakeSessionService(login_result=LoginThrottled(37))
    with client_for(service) as client:
        response = client.post(
            "/api/platform/session/login",
            headers={"Origin": ORIGIN},
            json={"username": "Alice", "password": "correct"},
        )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "37"
    assert response.json()["error"]["code"] == "login_throttled"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"username": "", "password": "do-not-echo"},
        {"username": "x" * 257, "password": "do-not-echo"},
        {"username": "Alice", "password": "x" * 1025},
        {"username": "Alice", "password": "secret", "role": "admin"},
    ],
)
def test_login_input_boundary_is_stable_and_never_echoes_password(body: dict[str, str]) -> None:
    service = FakeSessionService(login_result=issued())
    with client_for(service) as client:
        response = client.post(
            "/api/platform/session/login", headers={"Origin": ORIGIN}, json=body
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "do-not-echo" not in response.text and "secret" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert service.calls == []


def test_router_module_has_no_cockpit_command_or_websocket_imports() -> None:
    source = __import__("inspect").getsource(
        __import__("app.api.platform_session_router", fromlist=["*"])
    )
    assert "cockpit" not in source.lower()
    assert "command" not in source.lower()
    assert "websocket" not in source.lower()
