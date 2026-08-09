from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.models import (
    AuditDelivery,
    AuditEvent,
    AuditResult,
    PlatformSession,
    Role,
    User,
)
from app.platform.persistence import (
    AuditEventRepository,
    PlatformSessionRepository,
    UserRepository,
)
from app.platform.sanitization import sanitize_parameters

from .orm import AuditEventRow, PlatformSessionRow, UserRow

_TOKEN_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_PERSISTENCE_SENSITIVE_PARAMETER_KEYS = frozenset(
    {"rawsecret", "rawtoken", "sessionsecret", "privatetext"}
)


def _uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid UUID") from exc


def _optional_uuid(value: str | None, field_name: str) -> UUID | None:
    if value is None:
        return None
    return _uuid(value, field_name)


def _token_digest(value: str) -> str:
    if not isinstance(value, str) or _TOKEN_DIGEST_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "token_digest must be exactly 64 lowercase hexadecimal characters"
        )
    return value


def _utc_datetime(value: datetime, field_name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _optional_utc_datetime(
    value: datetime | None,
    field_name: str,
) -> datetime | None:
    if value is None:
        return None
    return _utc_datetime(value, field_name)


def _redact_persistence_sensitive_parameters(value: Any) -> Any:
    if isinstance(value, list):
        return [_redact_persistence_sensitive_parameters(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            rendered_key = str(key)
            normalized_key = "".join(
                character for character in rendered_key.lower() if character.isalnum()
            )
            redacted[rendered_key] = (
                "[redacted]"
                if normalized_key in _PERSISTENCE_SENSITIVE_PARAMETER_KEYS
                else _redact_persistence_sensitive_parameters(item)
            )
        return redacted
    return value


def _user_to_row(user: User) -> UserRow:
    disabled_at = _optional_utc_datetime(user.disabled_at, "user.disabled_at")
    created_at = _utc_datetime(user.created_at, "user.created_at")
    updated_at = _utc_datetime(user.updated_at, "user.updated_at")
    return UserRow(
        id=_uuid(user.id, "user.id"),
        username_norm=user.username_norm,
        display_name=user.display_name,
        password_hash=user.password_hash,
        role=user.role.value,
        disabled_at=disabled_at,
        created_at=created_at,
        updated_at=updated_at,
    )


def _user_from_row(row: UserRow) -> User:
    return User(
        id=str(row.id),
        username_norm=row.username_norm,
        display_name=row.display_name,
        password_hash=row.password_hash,
        role=Role(row.role),
        disabled_at=_optional_utc_datetime(row.disabled_at, "user.disabled_at"),
        created_at=_utc_datetime(row.created_at, "user.created_at"),
        updated_at=_utc_datetime(row.updated_at, "user.updated_at"),
    )


def _platform_session_to_row(platform_session: PlatformSession) -> PlatformSessionRow:
    token_digest = _token_digest(platform_session.token_digest)
    created_at = _utc_datetime(
        platform_session.created_at,
        "platform_session.created_at",
    )
    expires_at = _utc_datetime(
        platform_session.expires_at,
        "platform_session.expires_at",
    )
    last_seen_at = _optional_utc_datetime(
        platform_session.last_seen_at,
        "platform_session.last_seen_at",
    )
    revoked_at = _optional_utc_datetime(
        platform_session.revoked_at,
        "platform_session.revoked_at",
    )
    return PlatformSessionRow(
        id=_uuid(platform_session.id, "platform_session.id"),
        user_id=_uuid(platform_session.user_id, "platform_session.user_id"),
        token_digest=token_digest,
        created_at=created_at,
        expires_at=expires_at,
        last_seen_at=last_seen_at,
        revoked_at=revoked_at,
        revoke_reason=platform_session.revoke_reason,
    )


def _platform_session_from_row(row: PlatformSessionRow) -> PlatformSession:
    return PlatformSession(
        id=str(row.id),
        user_id=str(row.user_id),
        token_digest=_token_digest(row.token_digest),
        created_at=_utc_datetime(row.created_at, "platform_session.created_at"),
        expires_at=_utc_datetime(row.expires_at, "platform_session.expires_at"),
        last_seen_at=_optional_utc_datetime(
            row.last_seen_at,
            "platform_session.last_seen_at",
        ),
        revoked_at=_optional_utc_datetime(
            row.revoked_at,
            "platform_session.revoked_at",
        ),
        revoke_reason=row.revoke_reason,
    )


def _audit_event_to_row(event: AuditEvent) -> AuditEventRow:
    sanitized_parameters = cast(
        dict[str, Any],
        _redact_persistence_sensitive_parameters(
            sanitize_parameters(event.parameters)
        ),
    )
    occurred_at = _utc_datetime(event.occurred_at, "audit_event.occurred_at")
    return AuditEventRow(
        id=_uuid(event.id, "audit_event.id"),
        occurred_at=occurred_at,
        action=event.action,
        result=event.result.value,
        delivery=event.delivery.value,
        actor_role=event.actor_role.value if event.actor_role is not None else None,
        actor_user_id=_optional_uuid(event.actor_user_id, "audit_event.actor_user_id"),
        actor_platform_session_id=_optional_uuid(
            event.actor_platform_session_id,
            "audit_event.actor_platform_session_id",
        ),
        endpoint=event.endpoint,
        source_type=event.source_type,
        cockpit_session_id=event.cockpit_session_id,
        command_name=event.command_name,
        error_code=event.error_code,
        target_type=event.target_type,
        correlation_id=event.correlation_id,
        target_id=event.target_id,
        parameters=sanitized_parameters,
    )


def _audit_event_from_row(row: AuditEventRow) -> AuditEvent:
    return AuditEvent(
        id=str(row.id),
        occurred_at=_utc_datetime(row.occurred_at, "audit_event.occurred_at"),
        action=row.action,
        result=AuditResult(row.result),
        delivery=AuditDelivery(row.delivery),
        actor_user_id=str(row.actor_user_id) if row.actor_user_id is not None else None,
        actor_platform_session_id=(
            str(row.actor_platform_session_id)
            if row.actor_platform_session_id is not None
            else None
        ),
        actor_role=Role(row.actor_role) if row.actor_role is not None else None,
        endpoint=row.endpoint,
        cockpit_session_id=row.cockpit_session_id,
        command_name=row.command_name,
        correlation_id=row.correlation_id,
        target_type=row.target_type,
        target_id=row.target_id,
        parameters=dict(row.parameters),
        error_code=row.error_code,
        source_type=row.source_type,
    )


def _audit_event_values(event: AuditEvent) -> dict[str, Any]:
    row = _audit_event_to_row(event)
    return {column.name: getattr(row, column.name) for column in AuditEventRow.__table__.columns}


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        self._session.add(_user_to_row(user))

    async def get_by_id(self, user_id: str) -> User | None:
        statement = select(UserRow).where(UserRow.id == _uuid(user_id, "user_id"))
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return _user_from_row(row) if row is not None else None

    async def get_by_username_norm(self, username_norm: str) -> User | None:
        statement = select(UserRow).where(UserRow.username_norm == username_norm)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return _user_from_row(row) if row is not None else None


class SqlAlchemyPlatformSessionRepository(PlatformSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, platform_session: PlatformSession) -> None:
        self._session.add(_platform_session_to_row(platform_session))

    async def get_by_token_digest(self, token_digest: str) -> PlatformSession | None:
        token_digest = _token_digest(token_digest)
        statement = select(PlatformSessionRow).where(
            PlatformSessionRow.token_digest == token_digest
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return _platform_session_from_row(row) if row is not None else None


class SqlAlchemyAuditEventRepository(AuditEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: AuditEvent) -> bool:
        if event.delivery is AuditDelivery.LOST:
            raise ValueError("AuditDelivery.LOST has no persistence medium")

        values = _audit_event_values(event)
        await self._session.flush()
        statement = (
            insert(AuditEventRow)
            .values(values)
            .on_conflict_do_nothing(index_elements=[AuditEventRow.id])
        )
        result = cast(CursorResult[Any], await self._session.execute(statement))
        return result.rowcount == 1
