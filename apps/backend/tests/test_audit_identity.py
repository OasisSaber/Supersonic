from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.platform.audit_identity import (
    AuditEventConflict,
    audit_events_equivalent,
    require_matching_duplicate,
)
from app.platform.models import AuditDelivery, AuditEvent, AuditResult

EVENT = AuditEvent(
    id="11111111-1111-4111-8111-111111111111",
    occurred_at=datetime(2026, 8, 13, 12, tzinfo=UTC),
    action="cockpit.command",
    result=AuditResult.SUCCEEDED,
    delivery=AuditDelivery.FALLBACK,
    parameters={"command": "set_theme"},
)


def test_canonical_equality_normalizes_timezone_and_uuid_text() -> None:
    same = replace(
        EVENT,
        id=EVENT.id.upper(),
        occurred_at=EVENT.occurred_at.astimezone(
            timezone(timedelta(hours=8))
        ),
    )
    assert audit_events_equivalent(EVENT, same)


def test_canonical_equality_compares_sanitized_durable_payload() -> None:
    left = replace(EVENT, parameters={"raw_secret": "secret-a"})
    right = replace(EVENT, parameters={"raw_secret": "secret-b"})
    assert audit_events_equivalent(left, right)


def test_safe_persistent_difference_is_a_conflict() -> None:
    different = replace(EVENT, parameters={"command": "set_system_mode"})
    assert not audit_events_equivalent(EVENT, different)
    with pytest.raises(AuditEventConflict):
        require_matching_duplicate(EVENT, different)


def test_missing_duplicate_row_is_a_conflict() -> None:
    with pytest.raises(AuditEventConflict):
        require_matching_duplicate(None, EVENT)
