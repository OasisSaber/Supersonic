import ast
import inspect
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import get_type_hints
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.platform as platform
from app.adapters.postgres.orm import AuditEventRow, PlatformSessionRow, UserRow
from app.adapters.postgres.repositories import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyPlatformSessionRepository,
    SqlAlchemyUserRepository,
    _audit_event_from_row,
    _audit_event_to_row,
    _audit_event_values,
    _platform_session_from_row,
    _platform_session_to_row,
    _user_from_row,
    _user_to_row,
)
from app.platform.models import (
    AuditDelivery,
    AuditEvent,
    AuditRecord,
    AuditResult,
    PlatformSession,
    Principal,
    Role,
    User,
)
from app.platform.persistence import (
    AuditEventRepository,
    PlatformSessionRepository,
    PlatformUnitOfWork,
    UserRepository,
)

PLATFORM_DIR = Path(__file__).parents[1] / "app" / "platform"
FORBIDDEN_FRAMEWORKS = {"alembic", "fastapi", "psycopg", "sqlalchemy"}


def _audit_event_with_parameters(parameters: dict[str, object]) -> AuditEvent:
    return AuditEvent(
        id="11111111-1111-4111-8111-111111111111",
        occurred_at=datetime(2026, 8, 9, 12, tzinfo=UTC),
        action="audit.boundary.test",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
        parameters=parameters,
    )


def _platform_session_with_digest(token_digest: str) -> PlatformSession:
    created_at = datetime(2026, 8, 9, 12, tzinfo=UTC)
    return PlatformSession(
        id="22222222-2222-4222-8222-222222222222",
        user_id="33333333-3333-4333-8333-333333333333",
        token_digest=token_digest,
        created_at=created_at,
        expires_at=created_at + timedelta(hours=8),
    )


def _adapter_user() -> User:
    created_at = datetime(2026, 8, 9, 12, tzinfo=UTC)
    return User(
        id="44444444-4444-4444-8444-444444444444",
        username_norm="adapter-user",
        display_name="Adapter User",
        password_hash="$argon2id$adapter-test-hash",
        role=Role.OPERATOR,
        disabled_at=created_at + timedelta(hours=1),
        created_at=created_at,
        updated_at=created_at + timedelta(hours=2),
    )


def _adapter_audit_event() -> AuditEvent:
    return AuditEvent(
        id="55555555-5555-4555-8555-555555555555",
        occurred_at=datetime(2026, 8, 9, 12, tzinfo=UTC),
        action="audit.datetime.test",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
    )


def test_user_record_has_the_persistence_contract_shape() -> None:
    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    user = User(
        id="user-1",
        username_norm="oasis",
        display_name="Oasis",
        password_hash="argon2id-digest",
        role=Role.ADMIN,
        disabled_at=None,
        created_at=now,
        updated_at=now,
    )

    assert [item.name for item in fields(user)] == [
        "id",
        "username_norm",
        "display_name",
        "password_hash",
        "role",
        "disabled_at",
        "created_at",
        "updated_at",
    ]
    assert user.role is Role.ADMIN
    assert not hasattr(user, "__dict__")
    with pytest.raises(FrozenInstanceError):
        user.display_name = "Changed"  # type: ignore[misc]


def test_platform_session_record_has_the_persistence_contract_shape() -> None:
    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    platform_session = PlatformSession(
        id="platform-session-1",
        user_id="user-1",
        token_digest="sha256-digest",
        created_at=now,
        expires_at=now + timedelta(hours=8),
    )

    assert [item.name for item in fields(platform_session)] == [
        "id",
        "user_id",
        "token_digest",
        "created_at",
        "expires_at",
        "last_seen_at",
        "revoked_at",
        "revoke_reason",
    ]
    assert platform_session.last_seen_at is None
    assert platform_session.revoked_at is None
    assert platform_session.revoke_reason is None
    assert not hasattr(platform_session, "__dict__")


def test_platform_session_model_has_no_raw_secret_field() -> None:
    field_names = {item.name for item in fields(PlatformSession)}

    assert "token_digest" in field_names
    assert "token" not in field_names
    assert "secret" not in field_names


@pytest.mark.parametrize(
    "invalid_digest",
    ["a" * 63, "A" * 64, "g" * 64, "plaintext-session-token"],
    ids=["wrong-length", "uppercase", "non-hex", "plaintext"],
)
async def test_platform_session_add_rejects_invalid_digest_before_add(
    invalid_digest: str,
) -> None:
    session = AsyncSession()
    try:
        repository = SqlAlchemyPlatformSessionRepository(session)

        with pytest.raises(
            ValueError,
            match="token_digest must be exactly 64 lowercase hexadecimal characters",
        ):
            await repository.add(_platform_session_with_digest(invalid_digest))

        assert not session.new
    finally:
        await session.close()


@pytest.mark.parametrize(
    "invalid_digest",
    ["a" * 63, "A" * 64, "g" * 64, "plaintext-session-token"],
    ids=["wrong-length", "uppercase", "non-hex", "plaintext"],
)
async def test_platform_session_lookup_rejects_invalid_digest_before_sql(
    invalid_digest: str,
) -> None:
    session = AsyncSession()
    try:
        repository = SqlAlchemyPlatformSessionRepository(session)

        with pytest.raises(
            ValueError,
            match="token_digest must be exactly 64 lowercase hexadecimal characters",
        ):
            await repository.get_by_token_digest(invalid_digest)
    finally:
        await session.close()


def test_platform_session_row_rejects_invalid_digest_before_domain_mapping() -> None:
    created_at = datetime(2026, 8, 9, 12, tzinfo=UTC)
    row = PlatformSessionRow(
        id=UUID("22222222-2222-4222-8222-222222222222"),
        user_id=UUID("33333333-3333-4333-8333-333333333333"),
        token_digest="plaintext-session-token",
        created_at=created_at,
        expires_at=created_at + timedelta(hours=8),
        last_seen_at=None,
        revoked_at=None,
        revoke_reason=None,
    )

    with pytest.raises(
        ValueError,
        match="token_digest must be exactly 64 lowercase hexadecimal characters",
    ):
        _platform_session_from_row(row)


@pytest.mark.parametrize("field_name", ["disabled_at", "created_at", "updated_at"])
def test_user_to_row_rejects_each_naive_datetime(field_name: str) -> None:
    user = replace(
        _adapter_user(),
        **{field_name: datetime(2026, 8, 9, 12)},
    )

    with pytest.raises(ValueError, match=rf"user\.{field_name} must be timezone-aware"):
        _user_to_row(user)


@pytest.mark.parametrize("field_name", ["disabled_at", "created_at", "updated_at"])
def test_user_from_row_rejects_each_naive_datetime(field_name: str) -> None:
    user = _adapter_user()
    row = UserRow(
        id=UUID(user.id),
        username_norm=user.username_norm,
        display_name=user.display_name,
        password_hash=user.password_hash,
        role=user.role.value,
        disabled_at=user.disabled_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
    setattr(row, field_name, datetime(2026, 8, 9, 12))

    with pytest.raises(ValueError, match=rf"user\.{field_name} must be timezone-aware"):
        _user_from_row(row)


@pytest.mark.parametrize(
    "field_name",
    ["created_at", "expires_at", "last_seen_at", "revoked_at"],
)
def test_platform_session_to_row_rejects_each_naive_datetime(field_name: str) -> None:
    datetime_values = {
        "last_seen_at": datetime(2026, 8, 9, 13, tzinfo=UTC),
        "revoked_at": datetime(2026, 8, 9, 14, tzinfo=UTC),
    }
    datetime_values[field_name] = datetime(2026, 8, 9, 12)
    platform_session = replace(
        _platform_session_with_digest("a" * 64),
        **datetime_values,
    )

    with pytest.raises(
        ValueError,
        match=rf"platform_session\.{field_name} must be timezone-aware",
    ):
        _platform_session_to_row(platform_session)


@pytest.mark.parametrize(
    "field_name",
    ["created_at", "expires_at", "last_seen_at", "revoked_at"],
)
def test_platform_session_from_row_rejects_each_naive_datetime(
    field_name: str,
) -> None:
    platform_session = replace(
        _platform_session_with_digest("a" * 64),
        last_seen_at=datetime(2026, 8, 9, 13, tzinfo=UTC),
        revoked_at=datetime(2026, 8, 9, 14, tzinfo=UTC),
    )
    row = PlatformSessionRow(
        id=UUID(platform_session.id),
        user_id=UUID(platform_session.user_id),
        token_digest=platform_session.token_digest,
        created_at=platform_session.created_at,
        expires_at=platform_session.expires_at,
        last_seen_at=platform_session.last_seen_at,
        revoked_at=platform_session.revoked_at,
        revoke_reason=platform_session.revoke_reason,
    )
    setattr(row, field_name, datetime(2026, 8, 9, 12))

    with pytest.raises(
        ValueError,
        match=rf"platform_session\.{field_name} must be timezone-aware",
    ):
        _platform_session_from_row(row)


def test_audit_event_to_row_rejects_naive_occurred_at() -> None:
    event = replace(
        _adapter_audit_event(),
        occurred_at=datetime(2026, 8, 9, 12),
    )

    with pytest.raises(
        ValueError,
        match=r"audit_event\.occurred_at must be timezone-aware",
    ):
        _audit_event_to_row(event)


def test_audit_event_from_row_rejects_naive_occurred_at() -> None:
    event = _adapter_audit_event()
    row = AuditEventRow(
        id=UUID(event.id),
        occurred_at=datetime(2026, 8, 9, 12),
        action=event.action,
        result=event.result.value,
        delivery=event.delivery.value,
        actor_role=None,
        actor_user_id=None,
        actor_platform_session_id=None,
        endpoint=None,
        source_type=event.source_type,
        cockpit_session_id=None,
        command_name=None,
        error_code=None,
        target_type=None,
        correlation_id=None,
        target_id=None,
        parameters={},
    )

    with pytest.raises(
        ValueError,
        match=r"audit_event\.occurred_at must be timezone-aware",
    ):
        _audit_event_from_row(row)


def test_user_mapping_normalizes_aware_non_utc_datetimes_both_directions() -> None:
    china = timezone(timedelta(hours=8))
    local_times = {
        "disabled_at": datetime(2026, 8, 9, 12, tzinfo=china),
        "created_at": datetime(2026, 8, 9, 13, tzinfo=china),
        "updated_at": datetime(2026, 8, 9, 14, tzinfo=china),
    }
    expected = {
        "disabled_at": datetime(2026, 8, 9, 4, tzinfo=UTC),
        "created_at": datetime(2026, 8, 9, 5, tzinfo=UTC),
        "updated_at": datetime(2026, 8, 9, 6, tzinfo=UTC),
    }
    user = replace(_adapter_user(), **local_times)
    row_from_domain = _user_to_row(user)
    row_from_database = UserRow(
        id=UUID(user.id),
        username_norm=user.username_norm,
        display_name=user.display_name,
        password_hash=user.password_hash,
        role=user.role.value,
        **local_times,
    )
    domain_from_row = _user_from_row(row_from_database)

    for field_name, expected_value in expected.items():
        row_value = getattr(row_from_domain, field_name)
        domain_value = getattr(domain_from_row, field_name)
        assert row_value == expected_value and row_value.tzinfo is UTC
        assert domain_value == expected_value and domain_value.tzinfo is UTC


def test_platform_session_mapping_normalizes_non_utc_datetimes_both_directions() -> None:
    china = timezone(timedelta(hours=8))
    local_times = {
        "created_at": datetime(2026, 8, 9, 12, tzinfo=china),
        "expires_at": datetime(2026, 8, 9, 20, tzinfo=china),
        "last_seen_at": datetime(2026, 8, 9, 13, tzinfo=china),
        "revoked_at": datetime(2026, 8, 9, 14, tzinfo=china),
    }
    expected = {
        "created_at": datetime(2026, 8, 9, 4, tzinfo=UTC),
        "expires_at": datetime(2026, 8, 9, 12, tzinfo=UTC),
        "last_seen_at": datetime(2026, 8, 9, 5, tzinfo=UTC),
        "revoked_at": datetime(2026, 8, 9, 6, tzinfo=UTC),
    }
    platform_session = replace(
        _platform_session_with_digest("a" * 64),
        **local_times,
    )
    row_from_domain = _platform_session_to_row(platform_session)
    row_from_database = PlatformSessionRow(
        id=UUID(platform_session.id),
        user_id=UUID(platform_session.user_id),
        token_digest=platform_session.token_digest,
        revoke_reason=None,
        **local_times,
    )
    domain_from_row = _platform_session_from_row(row_from_database)

    for field_name, expected_value in expected.items():
        row_value = getattr(row_from_domain, field_name)
        domain_value = getattr(domain_from_row, field_name)
        assert row_value == expected_value and row_value.tzinfo is UTC
        assert domain_value == expected_value and domain_value.tzinfo is UTC


def test_audit_event_mapping_normalizes_non_utc_datetime_both_directions() -> None:
    china = timezone(timedelta(hours=8))
    local_time = datetime(2026, 8, 9, 12, tzinfo=china)
    expected = datetime(2026, 8, 9, 4, tzinfo=UTC)
    event = replace(_adapter_audit_event(), occurred_at=local_time)
    row_from_domain = _audit_event_to_row(event)
    row_from_database = AuditEventRow(
        id=UUID(event.id),
        occurred_at=local_time,
        action=event.action,
        result=event.result.value,
        delivery=event.delivery.value,
        actor_role=None,
        actor_user_id=None,
        actor_platform_session_id=None,
        endpoint=None,
        source_type=event.source_type,
        cockpit_session_id=None,
        command_name=None,
        error_code=None,
        target_type=None,
        correlation_id=None,
        target_id=None,
        parameters={},
    )
    domain_from_row = _audit_event_from_row(row_from_database)

    assert row_from_domain.occurred_at == expected
    assert row_from_domain.occurred_at.tzinfo is UTC
    assert domain_from_row.occurred_at == expected
    assert domain_from_row.occurred_at.tzinfo is UTC


async def test_user_datetime_validation_happens_before_add() -> None:
    session = AsyncSession()
    try:
        repository = SqlAlchemyUserRepository(session)
        user = replace(_adapter_user(), created_at=datetime(2026, 8, 9, 12))

        with pytest.raises(ValueError, match=r"user\.created_at must be timezone-aware"):
            await repository.add(user)

        assert not session.new
    finally:
        await session.close()


async def test_platform_session_datetime_validation_happens_before_add() -> None:
    session = AsyncSession()
    try:
        repository = SqlAlchemyPlatformSessionRepository(session)
        platform_session = replace(
            _platform_session_with_digest("a" * 64),
            revoked_at=datetime(2026, 8, 9, 12),
        )

        with pytest.raises(
            ValueError,
            match=r"platform_session\.revoked_at must be timezone-aware",
        ):
            await repository.add(platform_session)

        assert not session.new
    finally:
        await session.close()


async def test_audit_event_datetime_validation_happens_before_sql() -> None:
    session = AsyncSession()
    try:
        repository = SqlAlchemyAuditEventRepository(session)
        event = replace(
            _adapter_audit_event(),
            occurred_at=datetime(2026, 8, 9, 12),
        )

        with pytest.raises(
            ValueError,
            match=r"audit_event\.occurred_at must be timezone-aware",
        ):
            await repository.append(event)
    finally:
        await session.close()


def test_audit_event_record_has_the_persistence_contract_shape() -> None:
    occurred_at = datetime(2026, 8, 9, 12, tzinfo=UTC)
    event = AuditEvent(
        id="audit-event-1",
        occurred_at=occurred_at,
        action="set_theme",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
    )
    another_event = AuditEvent(
        id="audit-event-2",
        occurred_at=occurred_at,
        action="set_media_state",
        result=AuditResult.REJECTED,
        delivery=AuditDelivery.FALLBACK,
    )

    assert [item.name for item in fields(event)] == [
        "id",
        "occurred_at",
        "action",
        "result",
        "delivery",
        "actor_user_id",
        "actor_platform_session_id",
        "actor_role",
        "endpoint",
        "cockpit_session_id",
        "command_name",
        "correlation_id",
        "target_type",
        "target_id",
        "parameters",
        "error_code",
        "source_type",
    ]
    assert event.parameters == {}
    assert event.parameters is not another_event.parameters
    assert event.source_type == "local_hmi"
    assert not hasattr(event, "__dict__")


def test_audit_adapter_redacts_nested_secrets_before_row_construction() -> None:
    event = _audit_event_with_parameters(
        {"request": {"credentials": {"session_token": "raw-session-secret"}}}
    )

    row = _audit_event_to_row(event)

    assert row.parameters == {
        "request": {"credentials": {"session_token": "[redacted]"}}
    }


def test_audit_adapter_redacts_nested_private_text_before_row_construction() -> None:
    event = _audit_event_with_parameters(
        {"request": {"payload": {"message": "meet me at the private address"}}}
    )

    row = _audit_event_to_row(event)

    assert row.parameters == {"request": {"payload": {"message": "[redacted]"}}}


def test_audit_adapter_redacts_nested_private_paths_before_row_construction() -> None:
    event = _audit_event_with_parameters(
        {"request": {"payload": {"material_path": "C:/private/student/photo.png"}}}
    )

    row = _audit_event_to_row(event)

    assert row.parameters == {
        "request": {"payload": {"material_path": "[redacted]"}}
    }


def test_audit_adapter_truncates_nested_text_before_row_construction() -> None:
    event = _audit_event_with_parameters(
        {"request": {"payload": {"label": "x" * 161}}}
    )

    row = _audit_event_to_row(event)

    assert row.parameters == {
        "request": {"payload": {"label": ("x" * 160) + "…"}}
    }


def test_audit_adapter_sanitization_does_not_mutate_the_domain_event() -> None:
    parameters = {
        "request": {
            "token": "raw-token",
            "safe": {"label": "x" * 161},
        }
    }
    original_parameters = deepcopy(parameters)
    event = _audit_event_with_parameters(parameters)

    row = _audit_event_to_row(event)

    assert event.parameters == original_parameters
    assert row.parameters is not event.parameters
    assert row.parameters["request"] is not event.parameters["request"]


@pytest.mark.parametrize(
    "sensitive_key",
    ["raw_secret", "raw_token", "session_secret", "private_text"],
)
def test_audit_adapter_redacts_additional_nested_keys_before_row_and_sql(
    sensitive_key: str,
) -> None:
    parameters = {
        "request": {
            "nested": {
                sensitive_key: "must-not-persist",
                "safe_label": "visible",
            }
        }
    }
    original_parameters = deepcopy(parameters)
    event = _audit_event_with_parameters(parameters)
    expected_parameters = {
        "request": {
            "nested": {
                sensitive_key: "[redacted]",
                "safe_label": "visible",
            }
        }
    }

    row = _audit_event_to_row(event)
    insert_values = _audit_event_values(event)

    assert row.parameters == expected_parameters
    assert insert_values["parameters"] == expected_parameters
    assert event.parameters == original_parameters
    assert row.parameters is not event.parameters


@pytest.mark.parametrize("module_name", ["models.py", "persistence.py"])
def test_platform_core_has_no_framework_imports(module_name: str) -> None:
    source = (PLATFORM_DIR / module_name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.partition(".")[0])

    assert imported_roots.isdisjoint(FORBIDDEN_FRAMEWORKS)


@pytest.mark.parametrize(
    ("protocol", "method_names"),
    [
        (UserRepository, {"add", "get_by_id", "get_by_username_norm"}),
        (PlatformSessionRepository, {"add", "get_by_token_digest"}),
        (AuditEventRepository, {"append"}),
        (PlatformUnitOfWork, {"__aenter__", "__aexit__", "commit", "rollback"}),
    ],
)
def test_persistence_ports_define_async_protocol_methods(
    protocol: type,
    method_names: set[str],
) -> None:
    assert protocol._is_protocol is True
    for method_name in method_names:
        assert inspect.iscoroutinefunction(getattr(protocol, method_name))


def test_unit_of_work_exposes_repository_ports() -> None:
    annotations = get_type_hints(PlatformUnitOfWork)

    assert annotations == {
        "users": UserRepository,
        "platform_sessions": PlatformSessionRepository,
        "audit_events": AuditEventRepository,
    }


def test_existing_platform_records_and_public_exports_remain_available() -> None:
    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    principal = Principal("user-1", Role.OPERATOR, "session-1")
    record = AuditRecord(
        audit_id="audit-1",
        occurred_at=now,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        actor_session_id=principal.session_id,
        endpoint="control",
        command_name="set_theme",
        correlation_id="correlation-1",
        result=AuditResult.SUCCEEDED,
    )

    assert record.delivery is AuditDelivery.PRIMARY
    assert set(platform.__all__) == {
        "AuditBuffer",
        "AuditDelivery",
        "AuditFallback",
        "AuditRecord",
        "AuditResult",
        "AuditSink",
        "AuthorizedCockpitGateway",
        "GatewayResult",
        "InMemoryAuditSink",
        "JsonlAuditBuffer",
        "Principal",
        "Role",
        "RoleCommandPolicy",
    }
