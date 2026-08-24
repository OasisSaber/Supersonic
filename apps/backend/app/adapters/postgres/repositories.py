from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.audit_validation import validate_audit_event_runtime_types
from app.platform.models import (
    AuditCursor,
    AuditDelivery,
    AuditEvent,
    AuditPage,
    AuditQuery,
    AuditQueryScope,
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
from app.platform.sanitization import sanitize_audit_event

from .failures import KNOWN_DATABASE_FAILURES, database_unavailable
from .orm import AuditEventRow, PlatformSessionRow, UserRow

_TOKEN_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
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
        type(value) is not datetime
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
    validate_audit_event_runtime_types(event)
    sanitized_event = sanitize_audit_event(event)
    occurred_at = _utc_datetime(sanitized_event.occurred_at, "audit_event.occurred_at")
    return AuditEventRow(
        id=_uuid(sanitized_event.id, "audit_event.id"),
        occurred_at=occurred_at,
        action=sanitized_event.action,
        result=sanitized_event.result.value,
        delivery=sanitized_event.delivery.value,
        actor_role=(
            sanitized_event.actor_role.value if sanitized_event.actor_role is not None else None
        ),
        actor_user_id=_optional_uuid(
            sanitized_event.actor_user_id,
            "audit_event.actor_user_id",
        ),
        actor_platform_session_id=_optional_uuid(
            sanitized_event.actor_platform_session_id,
            "audit_event.actor_platform_session_id",
        ),
        endpoint=sanitized_event.endpoint,
        source_type=sanitized_event.source_type,
        cockpit_session_id=sanitized_event.cockpit_session_id,
        command_name=sanitized_event.command_name,
        error_code=sanitized_event.error_code,
        target_type=sanitized_event.target_type,
        correlation_id=sanitized_event.correlation_id,
        target_id=sanitized_event.target_id,
        parameters=cast(dict[str, Any], sanitized_event.parameters),
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

    async def list_all(self, limit: int) -> tuple[User, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        statement = select(UserRow).order_by(UserRow.username_norm.asc()).limit(limit)
        try:
            rows = (await self._session.execute(statement)).scalars().all()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return tuple(_user_from_row(row) for row in rows)

    async def set_role(
        self,
        user_id: str,
        role: Role,
        updated_at: datetime,
        *,
        expected_role: Role,
    ) -> bool:
        statement = (
            update(UserRow)
            .where(
                UserRow.id == _uuid(user_id, "user_id"),
                UserRow.role == expected_role.value,
            )
            .values(role=role.value, updated_at=_utc_datetime(updated_at, "updated_at"))
            .execution_options(preserve_rowcount=True)
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return result.rowcount == 1

    async def set_disabled(
        self,
        user_id: str,
        disabled_at: datetime | None,
        updated_at: datetime,
    ) -> bool:
        current_state_predicate = (
            UserRow.disabled_at.is_not(None)
            if disabled_at is None
            else UserRow.disabled_at.is_(None)
        )
        statement = (
            update(UserRow)
            .where(
                UserRow.id == _uuid(user_id, "user_id"),
                current_state_predicate,
            )
            .values(
                disabled_at=_optional_utc_datetime(disabled_at, "disabled_at"),
                updated_at=_utc_datetime(updated_at, "updated_at"),
            )
            .execution_options(preserve_rowcount=True)
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return result.rowcount == 1

    async def lock_enabled_role_holder_ids(self, role: Role) -> tuple[str, ...]:
        statement = (
            select(UserRow.id)
            .where(
                UserRow.role == role.value,
                UserRow.disabled_at.is_(None),
            )
            .order_by(UserRow.id.asc())
            .with_for_update()
        )
        try:
            rows = (await self._session.execute(statement)).scalars().all()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return tuple(str(value) for value in rows)

    async def get_by_id(self, user_id: str) -> User | None:
        statement = select(UserRow).where(UserRow.id == _uuid(user_id, "user_id"))
        try:
            row = (await self._session.execute(statement)).scalar_one_or_none()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return _user_from_row(row) if row is not None else None

    async def get_by_username_norm(self, username_norm: str) -> User | None:
        statement = select(UserRow).where(UserRow.username_norm == username_norm)
        try:
            row = (await self._session.execute(statement)).scalar_one_or_none()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return _user_from_row(row) if row is not None else None

    async def update_password_hash(
        self,
        user_id: str,
        password_hash: str,
        updated_at: datetime,
    ) -> bool:
        statement = (
            update(UserRow)
            .where(UserRow.id == _uuid(user_id, "user_id"))
            .values(
                password_hash=password_hash,
                updated_at=_utc_datetime(updated_at, "updated_at"),
            )
            .execution_options(preserve_rowcount=True)
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return result.rowcount == 1


class SqlAlchemyPlatformSessionRepository(PlatformSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, platform_session: PlatformSession) -> None:
        self._session.add(_platform_session_to_row(platform_session))

    async def list_for_user(
        self,
        user_id: str,
        limit: int,
    ) -> tuple[PlatformSession, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        statement = (
            select(PlatformSessionRow)
            .where(PlatformSessionRow.user_id == _uuid(user_id, "user_id"))
            .order_by(
                PlatformSessionRow.created_at.desc(),
                PlatformSessionRow.id.desc(),
            )
            .limit(limit)
        )
        try:
            rows = (await self._session.execute(statement)).scalars().all()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return tuple(_platform_session_from_row(row) for row in rows)

    async def revoke_all_for_user(
        self,
        user_id: str,
        revoked_at: datetime,
        reason: str,
    ) -> tuple[str, ...]:
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 128:
            raise ValueError("reason must be a non-empty string of at most 128 characters")
        statement = (
            update(PlatformSessionRow)
            .where(
                PlatformSessionRow.user_id == _uuid(user_id, "user_id"),
                PlatformSessionRow.revoked_at.is_(None),
            )
            .values(
                revoked_at=_utc_datetime(revoked_at, "revoked_at"),
                revoke_reason=reason,
            )
            .returning(PlatformSessionRow.id)
        )
        try:
            rows = (await self._session.execute(statement)).scalars().all()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return tuple(str(value) for value in rows)

    async def get_by_token_digest(self, token_digest: str) -> PlatformSession | None:
        token_digest = _token_digest(token_digest)
        statement = select(PlatformSessionRow).where(
            PlatformSessionRow.token_digest == token_digest
        )
        try:
            row = (await self._session.execute(statement)).scalar_one_or_none()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return _platform_session_from_row(row) if row is not None else None

    async def get_by_id(self, platform_session_id: str) -> PlatformSession | None:
        statement = select(PlatformSessionRow).where(
            PlatformSessionRow.id == _uuid(platform_session_id, "platform_session_id")
        )
        try:
            row = (await self._session.execute(statement)).scalar_one_or_none()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return _platform_session_from_row(row) if row is not None else None

    async def revoke(
        self,
        platform_session_id: str,
        revoked_at: datetime,
        reason: str | None,
    ) -> bool:
        if reason is not None and (
            not isinstance(reason, str) or not reason.strip() or len(reason) > 128
        ):
            raise ValueError("reason must be a non-empty string of at most 128 characters")
        statement = (
            update(PlatformSessionRow)
            .where(
                PlatformSessionRow.id
                == _uuid(platform_session_id, "platform_session_id"),
                PlatformSessionRow.revoked_at.is_(None),
            )
            .values(
                revoked_at=_utc_datetime(revoked_at, "revoked_at"),
                revoke_reason=reason,
            )
            .execution_options(preserve_rowcount=True)
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return result.rowcount == 1


class SqlAlchemyAuditEventRepository(AuditEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: AuditEvent) -> bool:
        validate_audit_event_runtime_types(event)
        if event.result is AuditResult.DEGRADED:
            raise ValueError("AuditResult.DEGRADED is not persistable")
        if event.delivery is AuditDelivery.LOST:
            raise ValueError("AuditDelivery.LOST has no persistence medium")

        values = _audit_event_values(event)
        try:
            await self._session.flush()
            statement = (
                insert(AuditEventRow)
                .values(values)
                .on_conflict_do_nothing(index_elements=[AuditEventRow.id])
                .execution_options(preserve_rowcount=True)
            )
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return result.rowcount == 1

    async def get_by_id(self, event_id: str) -> AuditEvent | None:
        statement = select(AuditEventRow).where(
            AuditEventRow.id == _uuid(event_id, "audit_event.id")
        )
        try:
            row = (await self._session.execute(statement)).scalar_one_or_none()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        return _audit_event_from_row(row) if row is not None else None

    async def list_page(self, query: AuditQuery) -> AuditPage:
        statement = select(AuditEventRow).order_by(
            AuditEventRow.occurred_at.desc(),
            AuditEventRow.id.desc(),
        )
        statement = _apply_audit_scope(statement, query.scope)
        if query.cursor is not None:
            statement = statement.where(_audit_keyset_before(query.cursor))
        statement = statement.limit(query.limit + 1)
        try:
            rows = (await self._session.execute(statement)).scalars().all()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        events = tuple(_audit_event_from_row(row) for row in rows[: query.limit])
        next_cursor = None
        if len(rows) > query.limit and events:
            final_event = events[-1]
            next_cursor = AuditCursor(
                occurred_at=final_event.occurred_at,
                event_id=final_event.id,
            )
        return AuditPage(events=events, next_cursor=next_cursor)


def _apply_audit_scope(
    statement: Any,
    scope: AuditQueryScope,
) -> Any:
    if scope is AuditQueryScope.ALL:
        return statement
    if scope is AuditQueryScope.OPERATIONAL:
        return statement.where(
            or_(
                AuditEventRow.action == "cockpit.command",
                AuditEventRow.action.like("cockpit.command.%"),
                AuditEventRow.action.like("risk.%"),
                AuditEventRow.action.like("recovery.%"),
            )
        )
    raise ValueError("audit query scope is not supported")


def _audit_keyset_before(cursor: AuditCursor) -> Any:
    cursor_id = _uuid(cursor.event_id, "cursor.event_id")
    cursor_time = _utc_datetime(cursor.occurred_at, "cursor.occurred_at")
    return or_(
        AuditEventRow.occurred_at < cursor_time,
        and_(
            AuditEventRow.occurred_at == cursor_time,
            AuditEventRow.id < cursor_id,
        ),
    )
