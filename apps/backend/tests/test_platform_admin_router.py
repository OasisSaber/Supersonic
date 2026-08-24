from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.platform_admin_router import create_platform_admin_router
from app.config import RuntimeSettings
from app.platform.admin import (
    AdminForbidden,
    AdminMutationFailed,
    AdminMutationResult,
    LastAdminProtected,
    SelfManagementForbidden,
    SessionSummary,
    UserSummary,
)
from app.platform.audit_identity import AuditEventConflict
from app.platform.errors import AuditUnavailable
from app.platform.models import (
    AuditCursor,
    AuditDelivery,
    AuditEvent,
    AuditPage,
    AuditResult,
    Principal,
    Role,
)
from app.platform.persistence import DatabaseUnavailable, MigrationRequired
from app.platform.sessions import InvalidSession, SessionIdentity

NOW = datetime(2026, 8, 21, 12, tzinfo=UTC)
ORIGIN = "http://127.0.0.1:5173"
COOKIE = "supersonic_platform_session_dev"


@dataclass
class FakeSessionResolver:
    result: SessionIdentity | Exception

    def __post_init__(self) -> None:
        self.calls: list[str] = []

    async def resolve(self, raw_secret: str) -> SessionIdentity:
        self.calls.append(raw_secret)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass
class FakeAdminService:
    users_result: tuple[UserSummary, ...] | Exception = ()
    sessions_result: tuple[SessionSummary, ...] | Exception = ()
    mutation_result: AdminMutationResult | Exception = AdminMutationResult(changed=False)

    def __post_init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def list_users(self, actor: Principal, *, limit: int = 100) -> tuple[UserSummary, ...]:
        self.calls.append(("list_users", actor, limit))
        if isinstance(self.users_result, Exception):
            raise self.users_result
        return self.users_result

    async def list_sessions(
        self, actor: Principal, user_id: str, *, limit: int = 100
    ) -> tuple[SessionSummary, ...]:
        self.calls.append(("list_sessions", actor, user_id, limit))
        if isinstance(self.sessions_result, Exception):
            raise self.sessions_result
        return self.sessions_result

    async def change_role(
        self, actor: Principal, user_id: str, new_role: Role
    ) -> AdminMutationResult:
        self.calls.append(("change_role", actor, user_id, new_role))
        return self._mutation()

    async def set_disabled(
        self, actor: Principal, user_id: str, *, disabled: bool
    ) -> AdminMutationResult:
        self.calls.append(("set_disabled", actor, user_id, disabled))
        return self._mutation()

    async def revoke_session(
        self,
        actor: Principal,
        platform_session_id: str,
        *,
        reason: str = "admin_revoke",
    ) -> AdminMutationResult:
        self.calls.append(("revoke_session", actor, platform_session_id, reason))
        return self._mutation()

    def _mutation(self) -> AdminMutationResult:
        if isinstance(self.mutation_result, Exception):
            raise self.mutation_result
        return self.mutation_result


@dataclass
class FakeAuditService:
    result: AuditPage | Exception = AuditPage(events=(), next_cursor=None)

    def __post_init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def list_for_role(self, role: Role, **_: object) -> AuditPage:
        self.calls.append(("list_for_role", role, _))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def identity(role: Role = Role.ADMIN) -> SessionIdentity:
    return SessionIdentity(
        principal=Principal("user-current", role, "session-current"),
        display_name="Current User",
        expires_at=NOW,
    )


def client_for(
    sessions: FakeSessionResolver,
    admin: object | None = None,
    audit: object | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_platform_admin_router(
            sessions=sessions,
            admin=admin or FakeAdminService(),
            audit=audit or FakeAuditService(),
            settings=RuntimeSettings(platform_ui_origin=ORIGIN),
        )
    )
    return TestClient(app)


def encoded_cursor_payload(payload: object) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def encoded_cursor_bytes(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def alternate_base64url_encoding(value: str) -> str:
    """Return a different unpadded spelling that decodes to the same bytes."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    unused_bits = {2: 4, 3: 2}[len(value) % 4]
    index = alphabet.index(value[-1])
    assert index % (1 << unused_bits) == 0
    alternate = value[:-1] + alphabet[index + 1]
    assert base64.urlsafe_b64decode(alternate + "=" * (-len(alternate) % 4)) == (
        base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    )
    return alternate


def test_admin_users_requires_platform_cookie_without_resolving() -> None:
    sessions = FakeSessionResolver(identity())

    with client_for(sessions) as client:
        response = client.get("/api/platform/admin/users")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": {
            "code": "session_required",
            "message": "A platform session is required.",
        }
    }
    assert sessions.calls == []


def test_authentication_precedes_get_query_validation() -> None:
    sessions = FakeSessionResolver(identity())

    with client_for(sessions) as client:
        users = client.get("/api/platform/admin/users?limit=0")
        audit = client.get("/api/platform/audit?cursor=not-a-cursor")

    for response in (users, audit):
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["error"]["code"] == "session_required"
    assert sessions.calls == []


def test_admin_users_resolves_cookie_and_returns_only_sanitized_summary() -> None:
    principal = identity().principal
    admin = FakeAdminService(
        users_result=(
            UserSummary(
                id="user-1",
                username_norm="alice",
                display_name="Alice",
                role=Role.OPERATOR,
                disabled_at=None,
                created_at=NOW,
                updated_at=NOW,
            ),
        )
    )

    with client_for(FakeSessionResolver(identity()), admin=admin) as client:
        client.cookies.set(COOKIE, "raw-secret-must-not-leak")
        response = client.get("/api/platform/admin/users?limit=7")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "users": [
            {
                "id": "user-1",
                "username": "alice",
                "displayName": "Alice",
                "role": "operator",
                "disabledAt": None,
                "createdAt": "2026-08-21T12:00:00Z",
                "updatedAt": "2026-08-21T12:00:00Z",
            }
        ]
    }
    assert admin.calls == [("list_users", principal, 7)]
    assert all(
        secret not in response.text
        for secret in ("password_hash", "passwordHash", "raw-secret", "token_digest")
    )


def test_admin_sessions_returns_no_token_material() -> None:
    admin = FakeAdminService(
        sessions_result=(
            SessionSummary(
                id="session-1",
                user_id="user-1",
                created_at=NOW,
                expires_at=NOW,
                last_seen_at=None,
                revoked_at=None,
                revoke_reason=None,
            ),
        )
    )

    with client_for(FakeSessionResolver(identity()), admin=admin) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.get("/api/platform/admin/users/user-1/sessions")

    assert response.status_code == 200
    assert response.json()["sessions"][0]["id"] == "session-1"
    assert all(
        secret not in response.text for secret in ("tokenDigest", "token_digest", "raw-secret")
    )


def test_non_admin_is_rejected_by_admin_service_not_router_ui_claims() -> None:
    current = identity(Role.VIEWER)
    admin = FakeAdminService(users_result=AdminForbidden())

    with client_for(FakeSessionResolver(current), admin=admin) as client:
        client.cookies.set(COOKIE, "viewer-secret")
        response = client.get("/api/platform/admin/users?role=admin")

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "admin_forbidden"
    assert admin.calls == [("list_users", current.principal, 100)]


@pytest.mark.parametrize("role", [Role.OPERATOR, Role.VIEWER])
def test_non_admin_mutation_is_rejected_by_server_service(role: Role) -> None:
    current = identity(role)
    admin = FakeAdminService(mutation_result=AdminForbidden())

    with client_for(FakeSessionResolver(current), admin=admin) as client:
        client.cookies.set(COOKIE, "non-admin-secret")
        response = client.post(
            "/api/platform/admin/users/user-1/disabled",
            headers={"Origin": ORIGIN},
            json={"disabled": True},
        )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "admin_forbidden"
    assert admin.calls == [("set_disabled", current.principal, "user-1", True)]


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (InvalidSession(), 401, "session_invalid"),
        (DatabaseUnavailable(), 503, "database_unavailable"),
        (MigrationRequired(), 503, "migration_required"),
    ],
)
def test_identity_failures_are_stable_no_store(error: Exception, status: int, code: str) -> None:
    with client_for(FakeSessionResolver(error)) as client:
        client.cookies.set(COOKIE, "unsafe-secret")
        response = client.get("/api/platform/admin/users")

    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == code
    assert "unsafe-secret" not in response.text


@pytest.mark.parametrize("limit", [0, 101, "not-an-int"])
def test_read_limit_is_bounded_with_stable_no_store_error(limit: object) -> None:
    admin = FakeAdminService()
    with client_for(FakeSessionResolver(identity()), admin=admin) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.get(f"/api/platform/admin/users?limit={limit}")

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "invalid_request"
    assert admin.calls == []


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/platform/admin/users/user-1/role", {"role": "viewer"}),
        ("/api/platform/admin/users/user-1/disabled", {"disabled": True}),
        ("/api/platform/admin/sessions/session-1/revoke", {"reason": "security_review"}),
    ],
)
@pytest.mark.parametrize("origin", [None, "null", ORIGIN + ".evil", ORIGIN + "/path"])
def test_admin_mutations_require_exact_origin_before_authentication(
    path: str, body: dict[str, object], origin: str | None
) -> None:
    sessions = FakeSessionResolver(identity())
    admin = FakeAdminService()
    headers = {} if origin is None else {"Origin": origin}

    with client_for(sessions, admin=admin) as client:
        response = client.post(path, headers=headers, json=body)

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "origin_forbidden"
    assert sessions.calls == []
    assert admin.calls == []


@pytest.mark.parametrize(
    ("path", "body", "expected_call"),
    [
        (
            "/api/platform/admin/users/user-1/role",
            {"role": "viewer"},
            ("change_role", "user-1", Role.VIEWER),
        ),
        (
            "/api/platform/admin/users/user-1/disabled",
            {"disabled": True},
            ("set_disabled", "user-1", True),
        ),
        (
            "/api/platform/admin/sessions/session-1/revoke",
            {"reason": "security_review"},
            ("revoke_session", "session-1", "security_review"),
        ),
    ],
)
def test_admin_mutations_use_server_principal_and_report_exact_degraded_ids(
    path: str,
    body: dict[str, object],
    expected_call: tuple[object, ...],
) -> None:
    current = identity()
    admin = FakeAdminService(
        mutation_result=AdminMutationResult(
            changed=True,
            revoked_session_ids=("session-1", "session-2"),
            revoke_propagation_failed_ids=("session-2",),
        )
    )

    with client_for(FakeSessionResolver(current), admin=admin) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.post(
            path,
            headers={"Origin": ORIGIN},
            json={**body, "clientRole": "admin"},
        )

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "invalid_request"
    assert admin.calls == []

    with client_for(FakeSessionResolver(current), admin=admin) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.post(
            path,
            headers={"Origin": ORIGIN},
            json=body,
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "changed": True,
        "revokedSessionIds": ["session-1", "session-2"],
        "revokePropagation": "degraded",
        "failedRevokePropagationSessionIds": ["session-2"],
    }
    assert admin.calls == [(expected_call[0], current.principal, *expected_call[1:])]


def test_complete_mutation_and_audit_conflict_have_stable_payloads() -> None:
    complete = FakeAdminService(mutation_result=AdminMutationResult(changed=False))
    conflict = FakeAdminService(mutation_result=AuditEventConflict("event-1"))

    with client_for(FakeSessionResolver(identity()), admin=complete) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.post(
            "/api/platform/admin/users/user-1/disabled",
            headers={"Origin": ORIGIN},
            json={"disabled": False},
        )
    assert response.json() == {
        "changed": False,
        "revokedSessionIds": [],
        "revokePropagation": "complete",
        "failedRevokePropagationSessionIds": [],
    }

    with client_for(FakeSessionResolver(identity()), admin=conflict) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.post(
            "/api/platform/admin/users/user-1/role",
            headers={"Origin": ORIGIN},
            json={"role": "viewer"},
        )
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "audit_conflict"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (SelfManagementForbidden(), 409, "self_management_forbidden"),
        (LastAdminProtected(), 409, "last_admin_protected"),
        (AdminMutationFailed(), 503, "admin_mutation_failed"),
        (AuditUnavailable("attempted audit unavailable"), 503, "audit_unavailable"),
        (DatabaseUnavailable(), 503, "database_unavailable"),
        (MigrationRequired(), 503, "migration_required"),
    ],
)
def test_mutation_service_failures_have_stable_no_store_mappings(
    error: Exception,
    status: int,
    code: str,
) -> None:
    admin = FakeAdminService(mutation_result=error)

    with client_for(FakeSessionResolver(identity()), admin=admin) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.post(
            "/api/platform/admin/users/user-1/role",
            headers={"Origin": ORIGIN},
            json={"role": "viewer"},
        )

    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/platform/admin/users/user-1/role", {}),
        ("/api/platform/admin/users/user-1/role", {"role": "superadmin"}),
        ("/api/platform/admin/users/user-1/disabled", {"disabled": "yes"}),
        ("/api/platform/admin/sessions/session-1/revoke", {"reason": "x" * 65}),
    ],
)
def test_mutation_bodies_are_strict_and_bounded(path: str, body: dict[str, object]) -> None:
    admin = FakeAdminService()
    with client_for(FakeSessionResolver(identity()), admin=admin) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.post(
            path,
            headers={"Origin": ORIGIN},
            json=body,
        )

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "invalid_request"
    assert admin.calls == []


def test_audit_scope_comes_only_from_resolved_principal_and_get_needs_no_origin() -> None:
    current = identity(Role.VIEWER)
    event = AuditEvent(
        id="11111111-1111-4111-8111-111111111111",
        occurred_at=NOW,
        action="cockpit.command",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
        actor_user_id="user-1",
        actor_platform_session_id="session-1",
        actor_role=Role.OPERATOR,
        parameters={"command": "set_theme"},
    )
    audit = FakeAuditService(result=AuditPage(events=(event,), next_cursor=None))

    with client_for(FakeSessionResolver(current), audit=audit) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.get(
            "/api/platform/audit?scope=all&limit=7",
            headers={"Origin": "https://untrusted.example.test"},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["events"] == [
        {
            "id": event.id,
            "occurredAt": "2026-08-21T12:00:00Z",
            "action": "cockpit.command",
            "result": "succeeded",
            "delivery": "primary",
            "actorUserId": "user-1",
            "actorPlatformSessionId": "session-1",
            "actorRole": "operator",
            "endpoint": None,
            "cockpitSessionId": None,
            "commandName": None,
            "correlationId": None,
            "targetType": None,
            "targetId": None,
            "parameters": {"command": "set_theme"},
            "errorCode": None,
            "sourceType": "local_hmi",
        }
    ]
    assert response.json()["nextCursor"] is None
    assert audit.calls == [("list_for_role", Role.VIEWER, {"cursor": None, "limit": 7})]


def test_audit_cursor_round_trips_and_invalid_cursor_is_stable() -> None:
    next_cursor = AuditCursor(
        occurred_at=NOW,
        event_id="22222222-2222-4222-8222-222222222222",
    )
    audit = FakeAuditService(result=AuditPage(events=(), next_cursor=next_cursor))

    with client_for(FakeSessionResolver(identity()), audit=audit) as client:
        client.cookies.set(COOKIE, "raw-secret")
        page = client.get("/api/platform/audit")
        encoded = page.json()["nextCursor"]
        follow_up = client.get(f"/api/platform/audit?cursor={encoded}")
        invalid = client.get("/api/platform/audit?cursor=not-a-cursor")

    assert follow_up.status_code == 200
    assert audit.calls[1] == (
        "list_for_role",
        Role.ADMIN,
        {"cursor": next_cursor, "limit": 50},
    )
    assert invalid.status_code == 422
    assert invalid.headers["cache-control"] == "no-store"
    assert invalid.json()["error"]["code"] == "invalid_cursor"


CANONICAL_CURSOR_PAYLOAD = {
    "t": "2026-08-21T12:00:00Z",
    "id": "22222222-2222-4222-8222-222222222222",
}
CANONICAL_CURSOR = encoded_cursor_payload(CANONICAL_CURSOR_PAYLOAD)
FRACTIONAL_CURSOR = encoded_cursor_payload(
    {**CANONICAL_CURSOR_PAYLOAD, "t": "2026-08-21T12:00:00.123456Z"}
)


INVALID_CURSOR_CASES = [
    ("", "explicit empty cursor"),
    ("x" * 513, "oversized cursor"),
    (f" {CANONICAL_CURSOR}", "leading whitespace"),
    (f"{CANONICAL_CURSOR}\n", "trailing whitespace"),
    (f"{CANONICAL_CURSOR}!", "non-base64url character"),
    (f"{CANONICAL_CURSOR}=", "explicit padding"),
    (alternate_base64url_encoding(FRACTIONAL_CURSOR), "alternate trailing bits"),
    ("A", "invalid base64url length"),
    (encoded_cursor_bytes(b"\xff"), "invalid UTF-8"),
    (encoded_cursor_bytes(b"{"), "malformed JSON"),
    (encoded_cursor_payload([]), "non-object JSON"),
    (encoded_cursor_payload({"t": CANONICAL_CURSOR_PAYLOAD["t"]}), "missing key"),
    (
        encoded_cursor_payload({**CANONICAL_CURSOR_PAYLOAD, "extra": True}),
        "extra key",
    ),
    (
        encoded_cursor_payload({**CANONICAL_CURSOR_PAYLOAD, "t": 1}),
        "wrong timestamp type",
    ),
    (
        encoded_cursor_payload(
            {**CANONICAL_CURSOR_PAYLOAD, "id": 22222222222242228222222222222222}
        ),
        "wrong UUID type",
    ),
    (
        encoded_cursor_payload({**CANONICAL_CURSOR_PAYLOAD, "id": "not-a-uuid"}),
        "invalid UUID",
    ),
    (
        encoded_cursor_payload(
            {
                **CANONICAL_CURSOR_PAYLOAD,
                "id": "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
            }
        ),
        "non-canonical UUID",
    ),
    (
        encoded_cursor_payload({**CANONICAL_CURSOR_PAYLOAD, "t": "2026-08-21T12:00:00"}),
        "naive timestamp",
    ),
    (
        encoded_cursor_payload({**CANONICAL_CURSOR_PAYLOAD, "t": "2026-08-21T20:00:00+08:00"}),
        "non-UTC timestamp",
    ),
    (
        encoded_cursor_payload({**CANONICAL_CURSOR_PAYLOAD, "t": "2026-08-21T12:00:00+00:00"}),
        "non-canonical UTC timestamp",
    ),
    (
        encoded_cursor_payload({**CANONICAL_CURSOR_PAYLOAD, "t": "2026-13-40T25:61:61Z"}),
        "invalid timestamp",
    ),
    (
        encoded_cursor_bytes(
            b'{ "id":"22222222-2222-4222-8222-222222222222", "t":"2026-08-21T12:00:00Z" }'
        ),
        "non-canonical JSON",
    ),
]


@pytest.mark.parametrize(
    ("value", "case"),
    INVALID_CURSOR_CASES,
    ids=[case for _, case in INVALID_CURSOR_CASES],
)
def test_audit_cursor_rejects_noncanonical_or_malformed_input_without_querying(
    value: str,
    case: str,
) -> None:
    audit = FakeAuditService()

    with client_for(FakeSessionResolver(identity()), audit=audit) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.get("/api/platform/audit", params={"cursor": value})

    assert response.status_code == 422, case
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": {
            "code": "invalid_cursor",
            "message": "Audit cursor is invalid.",
        }
    }
    assert audit.calls == []


def test_audit_cursor_encoder_normalizes_utc_uuid_and_is_deterministic() -> None:
    offset_cursor = AuditCursor(
        occurred_at=datetime(
            2026,
            8,
            21,
            20,
            tzinfo=timezone(timedelta(hours=8)),
        ),
        event_id="AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
    )
    audit = FakeAuditService(result=AuditPage(events=(), next_cursor=offset_cursor))

    with client_for(FakeSessionResolver(identity()), audit=audit) as client:
        client.cookies.set(COOKIE, "raw-secret")
        first = client.get("/api/platform/audit")
        second = client.get("/api/platform/audit")

    expected = encoded_cursor_payload(
        {
            "t": "2026-08-21T12:00:00Z",
            "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        }
    )
    assert first.json()["nextCursor"] == expected
    assert second.json()["nextCursor"] == expected
    assert "=" not in expected


def test_audit_service_value_error_is_not_mislabeled_as_invalid_cursor() -> None:
    audit = FakeAuditService(result=ValueError("audit service invariant failed"))

    with client_for(FakeSessionResolver(identity()), audit=audit) as client:
        client.cookies.set(COOKIE, "raw-secret")
        with pytest.raises(ValueError, match="audit service invariant failed"):
            client.get("/api/platform/audit")

    assert audit.calls == [("list_for_role", Role.ADMIN, {"cursor": None, "limit": 50})]


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (DatabaseUnavailable(), "database_unavailable"),
        (MigrationRequired(), "migration_required"),
    ],
)
def test_audit_persistence_failures_are_truthful_503(error: Exception, code: str) -> None:
    audit = FakeAuditService(result=error)
    with client_for(FakeSessionResolver(identity()), audit=audit) as client:
        client.cookies.set(COOKIE, "raw-secret")
        response = client.get("/api/platform/audit")

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == code
