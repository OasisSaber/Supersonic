from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, nullable=False)
    username_norm: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "char_length(username_norm) BETWEEN 1 AND 128",
            name="username_norm_length",
        ),
        CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 128",
            name="display_name_length",
        ),
        CheckConstraint(
            "role IN ('admin', 'operator', 'viewer')",
            name="role_allowed",
        ),
    )


class PlatformSessionRow(Base):
    __tablename__ = "platform_sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_digest: Mapped[str] = mapped_column(CHAR(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoke_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "token_digest ~ '^[0-9a-f]{64}$'",
            name="token_digest_format",
        ),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
        CheckConstraint(
            "revoke_reason IS NULL OR char_length(revoke_reason) <= 128",
            name="revoke_reason_length",
        ),
    )


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    delivery: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    actor_platform_session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    endpoint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    cockpit_session_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    command_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "result IN ('attempted', 'succeeded', 'rejected', 'error')",
            name="result_allowed",
        ),
        CheckConstraint(
            "delivery IN ('primary', 'fallback')",
            name="delivery_allowed",
        ),
        CheckConstraint(
            "actor_role IS NULL OR actor_role IN ('admin', 'operator', 'viewer')",
            name="actor_role_allowed",
        ),
        CheckConstraint("char_length(source_type) >= 1", name="source_type_nonempty"),
        Index(
            "ix_audit_events_occurred_at_id_desc",
            occurred_at.desc(),
            id.desc(),
        ),
    )
