from __future__ import annotations

from dataclasses import replace
from datetime import UTC
from uuid import UUID

from .audit_validation import validate_audit_event_runtime_types
from .models import AuditDelivery, AuditEvent, AuditResult
from .sanitization import sanitize_audit_event


class AuditEventConflict(RuntimeError):
    """The same audit UUID already identifies a different durable audit fact."""

    def __init__(self, event_id: str) -> None:
        super().__init__(f"Audit event {event_id} conflicts with an existing audit fact.")
        self.event_id = event_id


def canonicalize_persistable_audit_event(event: AuditEvent) -> AuditEvent:
    """Return the exact fact used for idempotency/conflict comparison."""
    validate_audit_event_runtime_types(event)
    if event.result is AuditResult.DEGRADED:
        raise ValueError("AuditResult.DEGRADED is not persistable")
    if event.delivery is AuditDelivery.LOST:
        raise ValueError("AuditDelivery.LOST has no persistence medium")
    if event.occurred_at.tzinfo is None or event.occurred_at.utcoffset() is None:
        raise ValueError("audit event occurred_at must be timezone-aware")

    sanitized = sanitize_audit_event(event)
    return replace(
        sanitized,
        id=_canonical_uuid(sanitized.id, "audit event id"),
        occurred_at=sanitized.occurred_at.astimezone(UTC),
        actor_user_id=_canonical_optional_uuid(
            sanitized.actor_user_id,
            "audit event actor_user_id",
        ),
        actor_platform_session_id=_canonical_optional_uuid(
            sanitized.actor_platform_session_id,
            "audit event actor_platform_session_id",
        ),
        parameters=dict(sanitized.parameters),
    )


def audit_events_equivalent(left: AuditEvent, right: AuditEvent) -> bool:
    """Compare durable canonical facts rather than unsafe input objects."""
    return (
        canonicalize_persistable_audit_event(left)
        == canonicalize_persistable_audit_event(right)
    )


def require_matching_duplicate(
    existing: AuditEvent | None,
    incoming: AuditEvent,
) -> None:
    """Accept a real idempotent duplicate and reject UUID/content collisions."""
    if existing is None or not audit_events_equivalent(existing, incoming):
        raise AuditEventConflict(incoming.id)


def _canonical_uuid(value: str, field_name: str) -> str:
    try:
        return str(UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid UUID") from error


def _canonical_optional_uuid(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _canonical_uuid(value, field_name)
