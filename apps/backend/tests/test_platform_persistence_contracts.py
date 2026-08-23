import ast
import inspect
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import cast, get_type_hints
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
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
        action="cockpit.command",
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
        action="cockpit.command",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
    )


class _NoSqlSession:
    async def flush(self) -> None:
        raise AssertionError("audit persistence must reject this event before flush")

    async def execute(self, statement: object) -> object:
        raise AssertionError("audit persistence must reject this event before execute")


class _PrivateDatetime(datetime):
    def isoformat(self, sep: str = "T", timespec: str = "auto") -> str:
        return "PRIVATE-occurred-at-value"


class _PrivateEnumLike:
    def __init__(self, value: str) -> None:
        self.value = value


class _Masquerade(str):
    def __new__(
        cls,
        private_value: str,
        allowed_value: str,
    ) -> "_Masquerade":
        instance = super().__new__(cls, private_value)
        instance._allowed_value = allowed_value
        return instance

    def __hash__(self) -> int:
        return hash(self._allowed_value)

    def __eq__(self, other: object) -> bool:
        return other == self._allowed_value


class _AuditInsertResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _RecordingAuditSession:
    def __init__(self, rowcount: int) -> None:
        self.calls: list[str] = []
        self.statements: list[object] = []
        self._rowcount = rowcount

    async def flush(self) -> None:
        self.calls.append("flush")

    async def execute(self, statement: object) -> _AuditInsertResult:
        self.calls.append("execute")
        self.statements.append(statement)
        return _AuditInsertResult(rowcount=self._rowcount)


class _IdempotentAuditSession:
    def __init__(self) -> None:
        self._event_ids: set[UUID] = set()

    async def flush(self) -> None:
        return None

    async def execute(self, statement: object) -> _AuditInsertResult:
        event_id = next(
            value
            for key, value in statement.compile().params.items()  # type: ignore[union-attr]
            if key.startswith("id")
        )
        if event_id in self._event_ids:
            return _AuditInsertResult(rowcount=0)
        self._event_ids.add(event_id)
        return _AuditInsertResult(rowcount=1)


async def test_degraded_audit_result_is_rejected_before_sql() -> None:
    event = replace(_adapter_audit_event(), result=AuditResult.DEGRADED)
    repository = SqlAlchemyAuditEventRepository(_NoSqlSession())

    with pytest.raises(
        ValueError,
        match="AuditResult.DEGRADED is not persistable",
    ):
        await repository.append(event)


async def test_lost_audit_delivery_is_rejected_before_sql() -> None:
    event = replace(_adapter_audit_event(), delivery=AuditDelivery.LOST)
    repository = SqlAlchemyAuditEventRepository(_NoSqlSession())

    with pytest.raises(
        ValueError,
        match="AuditDelivery.LOST has no persistence medium",
    ):
        await repository.append(event)


@pytest.mark.parametrize(
    ("field_name", "unsafe_value", "message"),
    [
        (
            "occurred_at",
            cast(datetime, _PrivateDatetime(2026, 8, 9, 12, tzinfo=UTC)),
            "occurred_at must be a datetime",
        ),
        (
            "result",
            cast(AuditResult, _PrivateEnumLike("PRIVATE-result-value")),
            "result must be an AuditResult",
        ),
        (
            "delivery",
            cast(AuditDelivery, _PrivateEnumLike("PRIVATE-delivery-value")),
            "delivery must be an AuditDelivery",
        ),
        (
            "actor_role",
            cast(Role, _PrivateEnumLike("PRIVATE-role-value")),
            "actor_role must be a Role or None",
        ),
    ],
)
async def test_audit_adapter_rejects_custom_runtime_values_before_sql(
    field_name: str,
    unsafe_value: object,
    message: str,
) -> None:
    repository = SqlAlchemyAuditEventRepository(_NoSqlSession())

    with pytest.raises(ValueError, match=message):
        await repository.append(replace(_adapter_audit_event(), **{field_name: unsafe_value}))


@pytest.mark.parametrize(
    ("field_name", "allowed_value"),
    [
        ("action", "cockpit.command"),
        ("endpoint", "center"),
        ("command_name", "set_theme"),
        ("target_type", "risk_event"),
        ("error_code", "risk_not_found"),
        ("source_type", "local_hmi"),
    ],
)
def test_audit_adapter_redacts_masquerading_metadata_before_row_construction(
    field_name: str,
    allowed_value: str,
) -> None:
    private_value = f"PRIVATE-{field_name}-value"

    row = _audit_event_to_row(
        replace(
            _adapter_audit_event(),
            **{field_name: _Masquerade(private_value, allowed_value)},
        )
    )

    assert getattr(row, field_name) == "[redacted]"
    assert private_value not in str(
        _audit_event_values(
            replace(
                _adapter_audit_event(),
                **{field_name: _Masquerade(private_value, allowed_value)},
            )
        )
    )


def test_audit_adapter_redacts_a_masquerading_safe_parameter_value() -> None:
    private_value = "PRIVATE-parameter-value"
    event = _audit_event_with_parameters({"command": _Masquerade(private_value, "set_theme")})

    row = _audit_event_to_row(event)

    assert row.parameters == {"command": "[redacted]"}
    assert private_value not in str(_audit_event_values(event))


def test_audit_adapter_drops_a_masquerading_safe_parameter_key() -> None:
    private_key = "PRIVATE-parameter-key"
    private_value = "PRIVATE-parameter-value"
    event = _audit_event_with_parameters(
        {
            _Masquerade(private_key, "command"): _Masquerade(
                private_value,
                "set_theme",
            )
        }
    )

    row = _audit_event_to_row(event)

    assert row.parameters == {}
    persisted = str(_audit_event_values(event))
    assert private_key not in persisted
    assert private_value not in persisted


@pytest.mark.parametrize(
    ("result", "delivery", "expected_result", "expected_delivery"),
    [
        (AuditResult.ATTEMPTED, AuditDelivery.PRIMARY, "attempted", "primary"),
        (AuditResult.SUCCEEDED, AuditDelivery.PRIMARY, "succeeded", "primary"),
        (AuditResult.REJECTED, AuditDelivery.FALLBACK, "rejected", "fallback"),
        (AuditResult.ERROR, AuditDelivery.FALLBACK, "error", "fallback"),
    ],
)
async def test_persistable_audit_result_delivery_pairs_emit_postgresql_insert_values(
    result: AuditResult,
    delivery: AuditDelivery,
    expected_result: str,
    expected_delivery: str,
) -> None:
    session = _RecordingAuditSession(rowcount=1)
    repository = SqlAlchemyAuditEventRepository(session)

    inserted = await repository.append(
        replace(_adapter_audit_event(), result=result, delivery=delivery)
    )
    statement = session.statements[0]
    compiled = statement.compile(dialect=postgresql.dialect())  # type: ignore[union-attr]

    assert inserted is True
    assert session.calls == ["flush", "execute"]
    assert str(compiled).startswith("INSERT INTO audit_events")
    assert compiled.params["result"] == expected_result
    assert compiled.params["delivery"] == expected_delivery


async def test_audit_append_returns_false_for_an_existing_event_id() -> None:
    repository = SqlAlchemyAuditEventRepository(_IdempotentAuditSession())
    event = replace(_adapter_audit_event(), id=str(uuid4()))

    assert await repository.append(event) is True
    assert await repository.append(event) is False


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


def test_audit_adapter_drops_unknown_nested_parameter_structure_before_row_construction() -> None:
    event = _audit_event_with_parameters(
        {"request": {"credentials": {"session_token": "raw-session-secret"}}}
    )

    row = _audit_event_to_row(event)

    assert row.parameters == {}


def test_audit_adapter_drops_unknown_nested_private_text_before_row_construction() -> None:
    event = _audit_event_with_parameters(
        {"request": {"payload": {"message": "meet me at the private address"}}}
    )

    row = _audit_event_to_row(event)

    assert row.parameters == {}


def test_audit_adapter_drops_unknown_nested_private_paths_before_row_construction() -> None:
    event = _audit_event_with_parameters(
        {"request": {"payload": {"material_path": "C:/private/student/photo.png"}}}
    )

    row = _audit_event_to_row(event)

    assert row.parameters == {}


def test_audit_adapter_redacts_uncontrolled_metadata_before_row_construction() -> None:
    private_text = "meet-alice-at-home"
    event = replace(
        _adapter_audit_event(),
        action=private_text,
        endpoint=private_text,
        cockpit_session_id=private_text,
        command_name=private_text,
        correlation_id=private_text,
        target_type=private_text,
        target_id=private_text,
        error_code=private_text,
        source_type=private_text,
    )

    row = _audit_event_to_row(event)

    assert row.action == "[redacted]"
    assert row.endpoint == "[redacted]"
    assert row.cockpit_session_id == "[redacted]"
    assert row.command_name == "[redacted]"
    assert row.correlation_id == "[redacted]"
    assert row.target_type == "[redacted]"
    assert row.target_id == "[redacted]"
    assert row.error_code == "[redacted]"
    assert row.source_type == "[redacted]"
    assert private_text not in str(_audit_event_values(event))


def test_audit_adapter_keeps_typed_safe_metadata_before_row_construction() -> None:
    event = replace(
        _adapter_audit_event(),
        action="risk.detected",
        endpoint="center",
        cockpit_session_id="22222222-2222-4222-8222-222222222222",
        command_name="acknowledge_risk",
        correlation_id="33333333-3333-4333-8333-333333333333",
        target_type="risk_event",
        target_id="simulated-takeover-11111111-1111-4111-8111-111111111111",
        error_code="risk_not_found",
        source_type="local_hmi",
    )

    row = _audit_event_to_row(event)

    assert row.action == event.action
    assert row.endpoint == event.endpoint
    assert row.cockpit_session_id == event.cockpit_session_id
    assert row.command_name == event.command_name
    assert row.correlation_id == event.correlation_id
    assert row.target_type == event.target_type
    assert row.target_id == event.target_id
    assert row.error_code == event.error_code
    assert row.source_type == event.source_type


@pytest.mark.parametrize(
    ("action", "parameters"),
    [
        (
            "user.role_change",
            {
                "oldRole": "operator",
                "newRole": "viewer",
                "revokedSessionCount": 2,
            },
        ),
        ("user.disable", {"revokedSessionCount": 2}),
        ("user.enable", {"revokedSessionCount": 0}),
        (
            "session.revoke",
            {
                "targetUserId": "11111111-1111-4111-8111-111111111111",
                "reason": "security_review",
            },
        ),
    ],
)
def test_audit_adapter_keeps_slice_e_security_facts(
    action: str,
    parameters: dict[str, object],
) -> None:
    event = replace(
        _adapter_audit_event(),
        action=action,
        target_type=("platform_session" if action == "session.revoke" else "user"),
        target_id="22222222-2222-4222-8222-222222222222",
        parameters=parameters,
    )

    row = _audit_event_to_row(event)

    assert row.action == action
    assert row.target_type == event.target_type
    assert row.target_id == event.target_id
    assert row.parameters == parameters


def test_audit_adapter_redacts_unapproved_slice_e_reason_and_parameter_values() -> None:
    private_reason = "meet-alice-at-home"
    event = replace(
        _adapter_audit_event(),
        action="session.revoke",
        target_type="platform_session",
        target_id="22222222-2222-4222-8222-222222222222",
        parameters={
            "targetUserId": "not-a-user-id",
            "reason": private_reason,
            "revokedSessionCount": -1,
            "oldRole": "owner",
            "newRole": "root",
        },
    )

    row = _audit_event_to_row(event)

    assert row.parameters == {
        "oldRole": "[redacted]",
        "newRole": "[redacted]",
        "revokedSessionCount": "[redacted]",
        "targetUserId": "[redacted]",
        "reason": "[redacted]",
    }
    assert private_reason not in repr(row.parameters)


def test_audit_adapter_redacts_sensitive_parameter_values_before_row_construction() -> None:
    raw_dsn = "postgresql+psycopg://audit:secret@db.example.test/audit"
    raw_sql = "SELECT * FROM private_audit_events"
    event = _audit_event_with_parameters({"database_dsn": raw_dsn, "sql_error": raw_sql})

    row = _audit_event_to_row(event)

    assert row.parameters == {"database_dsn": "[redacted]", "sql_error": "[redacted]"}
    assert raw_dsn not in str(_audit_event_values(event))
    assert raw_sql not in str(_audit_event_values(event))


def test_audit_adapter_drops_unknown_nested_text_before_row_construction() -> None:
    event = _audit_event_with_parameters({"request": {"payload": {"label": "x" * 161}}})

    row = _audit_event_to_row(event)

    assert row.parameters == {}


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
    assert row.parameters == {}


@pytest.mark.parametrize(
    "sensitive_key",
    ["raw_secret", "raw_token", "session_secret", "private_text"],
)
def test_audit_adapter_drops_unknown_nested_keys_before_row_and_sql(
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
    expected_parameters: dict[str, object] = {}

    row = _audit_event_to_row(event)
    insert_values = _audit_event_values(event)

    assert row.parameters == expected_parameters
    assert insert_values["parameters"] == expected_parameters
    assert event.parameters == original_parameters
    assert row.parameters is not event.parameters


def test_audit_adapter_drops_unknown_keys_and_free_form_text_before_row_and_sql() -> None:
    private_key = "C:/private/student/photo.png"
    private_text = "meet me behind the red building after class"
    event = _audit_event_with_parameters(
        {
            "command": "set_theme",
            "request": {"label": "visible", "detail": private_text},
            private_key: "visible",
        }
    )

    row = _audit_event_to_row(event)
    insert_values = _audit_event_values(event)

    expected = {"command": "set_theme"}
    assert row.parameters == expected
    assert insert_values["parameters"] == expected
    assert private_key not in str(insert_values)
    assert private_text not in str(insert_values)


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
