from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKeyConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.schema import PrimaryKeyConstraint, UniqueConstraint

from app.adapters.postgres.orm import AuditEventRow, Base, PlatformSessionRow, UserRow

EXPECTED_NULLABILITY = {
    "users": {
        "id": False,
        "username_norm": False,
        "display_name": False,
        "password_hash": False,
        "role": False,
        "disabled_at": True,
        "created_at": False,
        "updated_at": False,
    },
    "platform_sessions": {
        "id": False,
        "user_id": False,
        "token_digest": False,
        "created_at": False,
        "expires_at": False,
        "last_seen_at": True,
        "revoked_at": True,
        "revoke_reason": True,
    },
    "audit_events": {
        "id": False,
        "occurred_at": False,
        "action": False,
        "result": False,
        "delivery": False,
        "actor_role": True,
        "actor_user_id": True,
        "actor_platform_session_id": True,
        "endpoint": True,
        "source_type": False,
        "cockpit_session_id": True,
        "command_name": True,
        "error_code": True,
        "target_type": True,
        "correlation_id": True,
        "target_id": True,
        "parameters": False,
    },
}

EXPECTED_STRING_LENGTHS = {
    "users": {"username_norm": 128, "display_name": 128, "role": 16},
    "platform_sessions": {"revoke_reason": 128},
    "audit_events": {
        "action": 128,
        "result": 16,
        "delivery": 16,
        "actor_role": 16,
        "endpoint": 32,
        "source_type": 32,
        "cockpit_session_id": 80,
        "command_name": 64,
        "error_code": 64,
        "target_type": 64,
        "correlation_id": 64,
        "target_id": 128,
    },
}


def test_metadata_contains_only_platform_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "platform_sessions",
        "audit_events",
    }
    assert UserRow.__table__ is Base.metadata.tables["users"]
    assert PlatformSessionRow.__table__ is Base.metadata.tables["platform_sessions"]
    assert AuditEventRow.__table__ is Base.metadata.tables["audit_events"]


def test_metadata_uses_fixed_constraint_naming_convention() -> None:
    assert Base.metadata.naming_convention == {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


def test_columns_match_the_fixed_names_and_nullability() -> None:
    for table_name, expected_nullability in EXPECTED_NULLABILITY.items():
        table = Base.metadata.tables[table_name]

        assert set(table.columns.keys()) == set(expected_nullability)
        assert {
            column.name: column.nullable for column in table.columns
        } == expected_nullability


def test_uuid_json_text_and_character_types_are_exact() -> None:
    users = Base.metadata.tables["users"]
    sessions = Base.metadata.tables["platform_sessions"]
    audit_events = Base.metadata.tables["audit_events"]

    for column in (
        users.c.id,
        sessions.c.id,
        sessions.c.user_id,
        audit_events.c.id,
        audit_events.c.actor_user_id,
        audit_events.c.actor_platform_session_id,
    ):
        assert isinstance(column.type, PG_UUID)
        assert column.type.as_uuid is True

    assert isinstance(users.c.password_hash.type, Text)
    assert type(sessions.c.token_digest.type) is CHAR
    assert sessions.c.token_digest.type.length == 64
    assert isinstance(audit_events.c.parameters.type, JSONB)


def test_varchar_lengths_match_the_fixed_schema() -> None:
    for table_name, expected_lengths in EXPECTED_STRING_LENGTHS.items():
        table = Base.metadata.tables[table_name]

        for column_name, expected_length in expected_lengths.items():
            column_type = table.c[column_name].type
            assert type(column_type) is String
            assert column_type.length == expected_length


def test_all_timestamp_columns_are_timezone_aware() -> None:
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

    for table_name, expected_names in timestamp_columns.items():
        table = Base.metadata.tables[table_name]
        actual_names = {
            column.name for column in table.columns if isinstance(column.type, DateTime)
        }

        assert actual_names == expected_names
        assert all(table.c[name].type.timezone is True for name in expected_names)


def test_primary_unique_and_foreign_key_constraints_are_named() -> None:
    users = Base.metadata.tables["users"]
    sessions = Base.metadata.tables["platform_sessions"]
    audit_events = Base.metadata.tables["audit_events"]

    assert {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, PrimaryKeyConstraint)
    } == {"pk_users", "pk_platform_sessions", "pk_audit_events"}
    assert {
        constraint.name: tuple(constraint.columns.keys())
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {
        "uq_users_username_norm": ("username_norm",),
        "uq_platform_sessions_token_digest": ("token_digest",),
    }

    session_fk = next(
        constraint
        for constraint in sessions.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )
    actor_user_fk = next(
        constraint
        for constraint in audit_events.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )
    assert session_fk.name == "fk_platform_sessions_user_id_users"
    assert tuple(session_fk.columns.keys()) == ("user_id",)
    assert session_fk.elements[0].target_fullname == "users.id"
    assert session_fk.ondelete == "RESTRICT"
    assert actor_user_fk.name == "fk_audit_events_actor_user_id_users"
    assert tuple(actor_user_fk.columns.keys()) == ("actor_user_id",)
    assert actor_user_fk.elements[0].target_fullname == "users.id"
    assert actor_user_fk.ondelete == "RESTRICT"
    assert not audit_events.c.actor_platform_session_id.foreign_keys
    assert not users.foreign_key_constraints


def test_named_checks_enforce_platform_domain_constraints() -> None:
    actual_checks = {
        constraint.name: str(constraint.sqltext)
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert actual_checks == {
        "ck_users_username_norm_length": (
            "char_length(username_norm) BETWEEN 1 AND 128"
        ),
        "ck_users_display_name_length": "char_length(display_name) BETWEEN 1 AND 128",
        "ck_users_role_allowed": "role IN ('admin', 'operator', 'viewer')",
        "ck_platform_sessions_token_digest_format": (
            "token_digest ~ '^[0-9a-f]{64}$'"
        ),
        "ck_platform_sessions_expires_after_created": "expires_at > created_at",
        "ck_platform_sessions_revoke_reason_length": (
            "revoke_reason IS NULL OR char_length(revoke_reason) <= 128"
        ),
        "ck_audit_events_result_allowed": (
            "result IN ('attempted', 'succeeded', 'rejected', 'error')"
        ),
        "ck_audit_events_delivery_allowed": "delivery IN ('primary', 'fallback')",
        "ck_audit_events_actor_role_allowed": (
            "actor_role IS NULL OR actor_role IN ('admin', 'operator', 'viewer')"
        ),
        "ck_audit_events_source_type_nonempty": "char_length(source_type) >= 1",
    }


def test_audit_index_is_named_and_descending_on_time_then_id() -> None:
    indexes = list(Base.metadata.tables["audit_events"].indexes)

    assert len(indexes) == 1
    assert indexes[0].name == "ix_audit_events_occurred_at_id_desc"
    assert indexes[0].unique is False
    assert tuple(str(expression) for expression in indexes[0].expressions) == (
        "audit_events.occurred_at DESC",
        "audit_events.id DESC",
    )


def test_source_type_requires_an_explicit_application_value() -> None:
    source_type = Base.metadata.tables["audit_events"].c.source_type

    assert source_type.default is None
    assert source_type.server_default is None
