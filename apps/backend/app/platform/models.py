from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


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


@dataclass(frozen=True, slots=True)
class Principal:
    """Server-resolved identity. Never construct this from client role claims."""

    user_id: str
    role: Role
    session_id: str


@dataclass(frozen=True, slots=True)
class AuditRecord:
    audit_id: str
    occurred_at: datetime
    actor_user_id: str
    actor_role: Role
    actor_session_id: str
    endpoint: str
    command_name: str
    correlation_id: str
    result: AuditResult
    parameters: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    source_type: str = "local_hmi"
    delivery: AuditDelivery = AuditDelivery.PRIMARY
