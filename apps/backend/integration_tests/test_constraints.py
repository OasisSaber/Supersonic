from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import DateTime, create_engine, inspect, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.postgres.orm import AuditEventRow, PlatformSessionRow, UserRow


@pytest.fixture
def database_session(migrated_database_url: str) -> Iterator[Session]:
    engine = create_engine(migrated_database_url)
    try:
        with Session(engine) as session:
            yield session
            session.rollback()
    finally:
        engine.dispose()


def _user(**overrides: Any) -> UserRow:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "id": uuid4(),
        "username_norm": f"constraint-user-{uuid4().hex}",
        "display_name": "Constraint Test User",
        "password_hash": "$argon2id$constraint-test-only",
        "role": "operator",
        "disabled_at": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return UserRow(**values)


def _platform_session(user_id: UUID, **overrides: Any) -> PlatformSessionRow:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "id": uuid4(),
        "user_id": user_id,
        "token_digest": uuid4().hex + uuid4().hex,
        "created_at": now,
        "expires_at": now + timedelta(hours=1),
        "last_seen_at": None,
        "revoked_at": None,
        "revoke_reason": None,
    }
    values.update(overrides)
    return PlatformSessionRow(**values)


def _audit_event(**overrides: Any) -> AuditEventRow:
    values: dict[str, Any] = {
        "id": uuid4(),
        "occurred_at": datetime.now(UTC),
        "action": "constraint.test",
        "result": "succeeded",
        "delivery": "primary",
        "actor_role": "operator",
        "actor_user_id": None,
        "actor_platform_session_id": None,
        "endpoint": "center",
        "source_type": "integration_test",
        "cockpit_session_id": None,
        "command_name": None,
        "error_code": None,
        "target_type": None,
        "correlation_id": None,
        "target_id": None,
        "parameters": {"attempt": 1},
    }
    values.update(overrides)
    return AuditEventRow(**values)


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def test_duplicate_username_norm_is_rejected(database_session: Session) -> None:
    username_norm = f"duplicate-{uuid4().hex}"
    database_session.add(_user(username_norm=username_norm))
    database_session.flush()
    database_session.add(_user(username_norm=username_norm))

    with pytest.raises(IntegrityError) as caught:
        database_session.flush()
    database_session.rollback()

    assert _constraint_name(caught.value) == "uq_users_username_norm"


def test_user_role_outside_allowed_values_is_rejected(database_session: Session) -> None:
    database_session.add(_user(role="superuser"))

    with pytest.raises(IntegrityError) as caught:
        database_session.flush()
    database_session.rollback()

    assert _constraint_name(caught.value) == "ck_users_role_allowed"


def test_duplicate_token_digest_is_rejected(database_session: Session) -> None:
    user = _user()
    token_digest = "a" * 64
    database_session.add(user)
    database_session.flush()
    database_session.add(_platform_session(user.id, token_digest=token_digest))
    database_session.flush()
    database_session.add(_platform_session(user.id, token_digest=token_digest))

    with pytest.raises(IntegrityError) as caught:
        database_session.flush()
    database_session.rollback()

    assert _constraint_name(caught.value) == "uq_platform_sessions_token_digest"


@pytest.mark.parametrize(
    "token_digest",
    ["a" * 63, "A" * 64, "g" * 64],
    ids=["not-64-characters", "not-lowercase", "not-hexadecimal"],
)
def test_token_digest_outside_lowercase_hex_format_is_rejected(
    database_session: Session,
    token_digest: str,
) -> None:
    user = _user()
    database_session.add(user)
    database_session.flush()
    database_session.add(_platform_session(user.id, token_digest=token_digest))

    with pytest.raises(IntegrityError) as caught:
        database_session.flush()
    database_session.rollback()

    assert _constraint_name(caught.value) == "ck_platform_sessions_token_digest_format"


def test_platform_session_without_a_user_is_rejected(database_session: Session) -> None:
    database_session.add(_platform_session(uuid4()))

    with pytest.raises(IntegrityError) as caught:
        database_session.flush()
    database_session.rollback()

    assert _constraint_name(caught.value) == "fk_platform_sessions_user_id_users"


def test_user_with_a_platform_session_cannot_be_deleted(
    database_session: Session,
) -> None:
    user = _user()
    database_session.add(user)
    database_session.flush()
    database_session.add(_platform_session(user.id))
    database_session.flush()
    database_session.delete(user)

    with pytest.raises(IntegrityError) as caught:
        database_session.flush()
    database_session.rollback()

    assert _constraint_name(caught.value) == "fk_platform_sessions_user_id_users"


@pytest.mark.parametrize(
    "expires_offset",
    [timedelta(0), -timedelta(seconds=1)],
    ids=["equal-to-created", "before-created"],
)
def test_platform_session_must_expire_after_it_is_created(
    database_session: Session,
    expires_offset: timedelta,
) -> None:
    user = _user()
    created_at = datetime.now(UTC)
    database_session.add(user)
    database_session.flush()
    database_session.add(
        _platform_session(
            user.id,
            created_at=created_at,
            expires_at=created_at + expires_offset,
        )
    )

    with pytest.raises(IntegrityError) as caught:
        database_session.flush()
    database_session.rollback()

    assert _constraint_name(caught.value) == "ck_platform_sessions_expires_after_created"


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_constraint"),
    [
        ("delivery", "lost", "ck_audit_events_delivery_allowed"),
        ("result", "unknown", "ck_audit_events_result_allowed"),
    ],
    ids=["lost-delivery", "invalid-result"],
)
def test_invalid_audit_outcome_is_rejected(
    database_session: Session,
    field_name: str,
    invalid_value: str,
    expected_constraint: str,
) -> None:
    database_session.add(_audit_event(**{field_name: invalid_value}))

    with pytest.raises(IntegrityError) as caught:
        database_session.flush()
    database_session.rollback()

    assert _constraint_name(caught.value) == expected_constraint


def test_audit_actor_user_reference_prevents_user_deletion(
    database_session: Session,
) -> None:
    user = _user()
    database_session.add(user)
    database_session.flush()
    database_session.add(_audit_event(actor_user_id=user.id))
    database_session.flush()
    database_session.delete(user)

    with pytest.raises(IntegrityError) as caught:
        database_session.flush()
    database_session.rollback()

    assert _constraint_name(caught.value) == "fk_audit_events_actor_user_id_users"


def test_audit_actor_platform_session_can_reference_a_missing_id(
    database_session: Session,
) -> None:
    missing_session_id = uuid4()
    audit_event = _audit_event(actor_platform_session_id=missing_session_id)

    database_session.add(audit_event)
    database_session.flush()
    database_session.expire(audit_event)

    stored = database_session.get(AuditEventRow, audit_event.id)
    assert stored is not None
    assert stored.actor_platform_session_id == missing_session_id


def test_audit_actor_platform_session_reference_survives_session_cleanup(
    database_session: Session,
) -> None:
    user = _user()
    platform_session = _platform_session(user.id)
    audit_event = _audit_event(
        actor_user_id=user.id,
        actor_platform_session_id=platform_session.id,
    )
    database_session.add(user)
    database_session.flush()
    database_session.add(platform_session)
    database_session.flush()
    database_session.add(audit_event)
    database_session.flush()

    database_session.delete(platform_session)
    database_session.flush()
    database_session.expire(audit_event)

    stored = database_session.get(AuditEventRow, audit_event.id)
    assert stored is not None
    assert stored.actor_platform_session_id == platform_session.id


def test_postgresql_types_and_audit_ordering_index_exist(
    database_session: Session,
) -> None:
    occurred_at = datetime(2026, 8, 9, 9, 30, tzinfo=UTC)
    parameters = {"nested": {"enabled": True}, "attempts": [1, 2]}
    audit_event = _audit_event(occurred_at=occurred_at, parameters=parameters)
    database_session.add(audit_event)
    database_session.flush()
    database_session.expire(audit_event)

    stored = database_session.scalar(
        select(AuditEventRow).where(AuditEventRow.id == audit_event.id)
    )
    assert stored is not None
    assert stored.parameters == parameters
    assert stored.occurred_at.utcoffset() is not None

    inspector = inspect(database_session.connection())
    audit_columns = {
        column["name"]: column for column in inspector.get_columns("audit_events")
    }
    assert isinstance(audit_columns["parameters"]["type"], JSONB)

    timestamp_columns = {
        "users": {"disabled_at", "created_at", "updated_at"},
        "platform_sessions": {
            "created_at",
            "expires_at",
            "last_seen_at",
            "revoked_at",
        },
        "audit_events": {"occurred_at"},
    }
    for table_name, column_names in timestamp_columns.items():
        reflected_columns = {
            column["name"]: column for column in inspector.get_columns(table_name)
        }
        for column_name in column_names:
            reflected_type = reflected_columns[column_name]["type"]
            assert isinstance(reflected_type, DateTime)
            assert reflected_type.timezone is True

    audit_indexes = {
        index["name"]: index for index in inspector.get_indexes("audit_events")
    }
    ordering_index = audit_indexes["ix_audit_events_occurred_at_id_desc"]
    assert ordering_index["column_names"] == ["occurred_at", "id"]
    assert ordering_index["unique"] is False
    assert "desc" in ordering_index["column_sorting"]["occurred_at"]
    assert "desc" in ordering_index["column_sorting"]["id"]


def test_database_schema_contains_only_digest_and_hash_secret_columns(
    database_session: Session,
) -> None:
    inspector = inspect(database_session.connection())
    table_columns = {
        table_name: {
            column["name"] for column in inspector.get_columns(table_name)
        }
        for table_name in ("users", "platform_sessions", "audit_events")
    }
    all_columns = set().union(*table_columns.values())

    assert {"raw_secret", "token", "password"}.isdisjoint(all_columns)
    assert "password_hash" in table_columns["users"]
    assert "token_digest" in table_columns["platform_sessions"]
    assert {
        column_name
        for column_name in all_columns
        if "password" in column_name or "secret" in column_name or "token" in column_name
    } == {"password_hash", "token_digest"}
