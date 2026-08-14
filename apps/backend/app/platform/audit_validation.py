from __future__ import annotations

from datetime import datetime

from .models import AuditDelivery, AuditEvent, AuditResult, Role


def validate_audit_event_runtime_types(event: AuditEvent) -> None:
    """Reject runtime lookalikes before a durable audit boundary uses their methods."""
    if type(event) is not AuditEvent:
        raise ValueError("audit event must be an AuditEvent")
    if type(event.id) is not str:
        raise ValueError("audit event id must be a string")
    if type(event.occurred_at) is not datetime:
        raise ValueError("audit event occurred_at must be a datetime")
    if type(event.result) is not AuditResult:
        raise ValueError("audit event result must be an AuditResult")
    if type(event.delivery) is not AuditDelivery:
        raise ValueError("audit event delivery must be an AuditDelivery")
    if event.actor_role is not None and type(event.actor_role) is not Role:
        raise ValueError("audit event actor_role must be a Role or None")
    if event.actor_user_id is not None and type(event.actor_user_id) is not str:
        raise ValueError("audit event actor_user_id must be a string or None")
    if (
        event.actor_platform_session_id is not None
        and type(event.actor_platform_session_id) is not str
    ):
        raise ValueError(
            "audit event actor_platform_session_id must be a string or None"
        )
