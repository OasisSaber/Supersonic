from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AuditResult(StrEnum):
    ATTEMPTED = "attempted"
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    ERROR = "error"
    # Compatibility value from the v3 draft. New code records delivery separately.
    DEGRADED = "degraded"


class AuditDelivery(StrEnum):
    PRIMARY = "primary"
    FALLBACK = "fallback"
    LOST = "lost"


class AuditQueryScope(StrEnum):
    """The fixed audit visibility sets supported by the persistence port."""

    ALL = "all"
    OPERATIONAL = "operational"


@dataclass(frozen=True, slots=True)
class User:
    id: str
    username_norm: str
    display_name: str
    password_hash: str
    role: Role
    disabled_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlatformSession:
    id: str
    user_id: str
    token_digest: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    occurred_at: datetime
    action: str
    result: AuditResult
    delivery: AuditDelivery
    actor_user_id: str | None = None
    actor_platform_session_id: str | None = None
    actor_role: Role | None = None
    endpoint: str | None = None
    cockpit_session_id: str | None = None
    command_name: str | None = None
    correlation_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    source_type: str = "local_hmi"


@dataclass(frozen=True, slots=True)
class AuditCursor:
    """Stable descending keyset position for audit-history reads."""

    occurred_at: datetime
    event_id: str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("cursor.occurred_at must be timezone-aware")
        try:
            UUID(self.event_id)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("cursor.event_id must be a valid UUID") from error
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class AuditQuery:
    scope: AuditQueryScope
    cursor: AuditCursor | None
    limit: int

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 100:
            raise ValueError("limit must be between 1 and 100")


@dataclass(frozen=True, slots=True)
class AuditPage:
    events: tuple[AuditEvent, ...]
    next_cursor: AuditCursor | None


@dataclass(frozen=True, slots=True)
class Principal:
    """Server-resolved identity. Never construct this from client role claims."""

    user_id: str
    role: Role
    session_id: str


