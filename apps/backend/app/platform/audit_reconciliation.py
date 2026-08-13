from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from .audit_fallback import JsonlAuditFallback
from .audit_identity import (
    audit_events_equivalent,
    require_matching_duplicate,
)
from .audit_validation import validate_audit_event_runtime_types
from .models import AuditDelivery, AuditEvent, AuditResult
from .persistence import PlatformUnitOfWork
from .sanitization import sanitize_audit_event


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> PlatformUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class AuditReconciliationReport:
    validated: int
    imported: int
    duplicates: int
    dry_run: bool


class AuditReconciler:
    """Import already-sanitized fallback facts without replaying any command."""

    def __init__(self, *, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def reconcile(
        self,
        events: Sequence[AuditEvent],
        *,
        dry_run: bool,
    ) -> AuditReconciliationReport:
        prepared = tuple(_prepare_event(event) for event in events)
        _validate_batch_identity(prepared)

        if dry_run:
            return AuditReconciliationReport(
                validated=len(prepared),
                imported=0,
                duplicates=0,
                dry_run=True,
            )

        imported = 0
        duplicates = 0
        async with self._uow_factory() as uow:
            for event in prepared:
                if await uow.audit_events.append(event):
                    imported += 1
                    continue

                existing = await uow.audit_events.get_by_id(event.id)
                require_matching_duplicate(existing, event)
                duplicates += 1

            await uow.commit()

        return AuditReconciliationReport(
            validated=len(prepared),
            imported=imported,
            duplicates=duplicates,
            dry_run=False,
        )

    async def reconcile_file(
        self,
        fallback: JsonlAuditFallback,
        *,
        dry_run: bool,
    ) -> AuditReconciliationReport:
        with fallback.locked():
            if not fallback.path.is_file():
                raise FileNotFoundError("Audit fallback file does not exist.")
            events, fingerprint = fallback.load_events_with_fingerprint_locked()
            report = await self.reconcile(events, dry_run=dry_run)
            if not dry_run:
                if not fallback.matches_fingerprint_locked(fingerprint):
                    raise RuntimeError("Audit fallback changed during reconciliation.")
                _archive_after_success(fallback.path)
            return report


def _validate_batch_identity(events: Sequence[AuditEvent]) -> None:
    by_id: dict[str, AuditEvent] = {}
    for event in events:
        existing = by_id.get(event.id)
        if existing is None:
            by_id[event.id] = event
            continue
        if not audit_events_equivalent(existing, event):
            require_matching_duplicate(existing, event)


def _prepare_event(event: AuditEvent) -> AuditEvent:
    validate_audit_event_runtime_types(event)
    if event.delivery is not AuditDelivery.FALLBACK:
        raise ValueError("Audit reconciliation delivery must be fallback")
    if event.result is AuditResult.DEGRADED:
        raise ValueError("Audit reconciliation result must be persistable")
    try:
        canonical_id = str(UUID(event.id))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Audit reconciliation event id must be a valid UUID") from error
    if event.occurred_at.tzinfo is None or event.occurred_at.utcoffset() is None:
        raise ValueError("Audit reconciliation occurred_at must be timezone-aware")
    if not isinstance(event.action, str) or not event.action:
        raise ValueError("Audit reconciliation action must be a non-empty string")
    if not isinstance(event.source_type, str) or not event.source_type:
        raise ValueError("Audit reconciliation source_type must be a non-empty string")

    sanitized = sanitize_audit_event(event)
    parameters = sanitized.parameters
    if not isinstance(parameters, dict):
        raise ValueError("Audit reconciliation parameters must sanitize to an object")

    return replace(
        sanitized,
        id=canonical_id,
        occurred_at=sanitized.occurred_at.astimezone(UTC),
        actor_user_id=_optional_uuid_text(sanitized.actor_user_id),
        actor_platform_session_id=_optional_uuid_text(
            sanitized.actor_platform_session_id
        ),
        parameters=cast(dict[str, Any], parameters),
    )


def _optional_uuid_text(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Audit reconciliation actor id must be a valid UUID") from error


def _archive_after_success(source: Path) -> Path:
    archive = source.with_name(f"{source.name}.reconciled-{uuid4().hex}")
    os.link(source, archive)
    try:
        _remove_source(source)
    except OSError:
        try:
            archive.unlink()
        except OSError as cleanup_error:
            raise RuntimeError("Audit reconciliation archive cleanup failed.") from cleanup_error
        raise
    return archive


def _remove_source(source: Path) -> None:
    source.unlink()
