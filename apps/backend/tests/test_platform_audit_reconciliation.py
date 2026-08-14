from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

from app.platform import audit_reconciliation
from app.platform.audit_fallback import AuditFallbackBusy, JsonlAuditFallback
from app.platform.audit_reconciliation import AuditReconciler
from app.platform.models import AuditDelivery, AuditEvent, AuditResult, Role

EVENT = AuditEvent(
    id="11111111-1111-4111-8111-111111111111",
    occurred_at=datetime(2026, 8, 13, 12, tzinfo=UTC),
    action="cockpit.command",
    result=AuditResult.SUCCEEDED,
    delivery=AuditDelivery.FALLBACK,
    parameters={"command": "set_theme"},
)


class _PrivateDatetime(datetime):
    def isoformat(self, sep: str = "T", timespec: str = "auto") -> str:
        return "PRIVATE-occurred-at-value"


class _PrivateEnumLike:
    def __init__(self, value: str) -> None:
        self.value = value


class _Repository:
    def __init__(self, inserts: list[bool], *, error: Exception | None = None) -> None:
        self._inserts = iter(inserts)
        self._error = error
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> bool:
        self.events.append(event)
        if self._error is not None:
            raise self._error
        return next(self._inserts)

    async def get_by_id(self, event_id: str) -> AuditEvent | None:
        for event in reversed(self.events):
            if event.id == event_id:
                return event
        return None

    async def list_page(self, query: object) -> object:
        raise AssertionError(f"reconciliation must not query audit history: {query}")


class _SourceAppendAttemptRepository(_Repository):
    def __init__(self, fallback: JsonlAuditFallback) -> None:
        super().__init__([True])
        self._fallback = fallback
        self.busy = False

    async def append(self, event: AuditEvent) -> bool:
        inserted = await super().append(event)
        try:
            self._fallback.append(
                replace(EVENT, id="22222222-2222-4222-8222-222222222222")
            )
        except AuditFallbackBusy:
            self.busy = True
        return inserted


class _UnitOfWork:
    def __init__(self, repository: _Repository) -> None:
        self.audit_events = repository
        self.committed = False
        self.exited = False

    async def __aenter__(self) -> _UnitOfWork:
        return self

    async def __aexit__(self, *args: object) -> None:
        self.exited = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        raise AssertionError("the context manager owns rollback behavior")


async def test_dry_run_validates_without_constructing_a_unit_of_work() -> None:
    reconciler = AuditReconciler(
        uow_factory=lambda: (_ for _ in ()).throw(AssertionError("no uow"))
    )

    report = await reconciler.reconcile([EVENT], dry_run=True)

    assert report.validated == 1
    assert report.imported == 0
    assert report.duplicates == 0
    assert report.dry_run is True


async def test_reconciliation_commits_once_and_reports_inserted_and_duplicate_events() -> None:
    repository = _Repository([True, False])
    uow = _UnitOfWork(repository)
    reconciler = AuditReconciler(uow_factory=lambda: uow)

    report = await reconciler.reconcile([EVENT, EVENT], dry_run=False)

    assert report.validated == 2
    assert report.imported == 1
    assert report.duplicates == 1
    assert report.dry_run is False
    assert repository.events == [EVENT, EVENT]
    assert uow.committed is True
    assert uow.exited is True


@pytest.mark.parametrize(
    "invalid_event",
    [
        EVENT.__class__(
            id=EVENT.id,
            occurred_at=EVENT.occurred_at,
            action=EVENT.action,
            result=EVENT.result,
            delivery=AuditDelivery.PRIMARY,
        ),
        EVENT.__class__(
            id=EVENT.id,
            occurred_at=EVENT.occurred_at,
            action=EVENT.action,
            result=EVENT.result,
            delivery=AuditDelivery.LOST,
        ),
    ],
)
async def test_reconciliation_rejects_nonfallback_delivery_before_database_work(
    invalid_event: AuditEvent,
) -> None:
    reconciler = AuditReconciler(
        uow_factory=lambda: (_ for _ in ()).throw(AssertionError("no uow"))
    )

    with pytest.raises(ValueError, match="delivery must be fallback"):
        await reconciler.reconcile([invalid_event], dry_run=False)


@pytest.mark.parametrize(
    ("field_name", "unsafe_value", "message"),
    [
        (
            "occurred_at",
            cast(datetime, _PrivateDatetime(2026, 8, 13, 12, tzinfo=UTC)),
            "occurred_at must be a datetime",
        ),
        (
            "result",
            cast(AuditResult, _PrivateEnumLike("PRIVATE-result-value")),
            "result must be an AuditResult",
        ),
        (
            "delivery",
            cast(AuditDelivery, _PrivateEnumLike("PRIVATE-delivery-value")),
            "delivery must be an AuditDelivery",
        ),
        (
            "actor_role",
            cast(Role, _PrivateEnumLike("PRIVATE-role-value")),
            "actor_role must be a Role or None",
        ),
    ],
)
async def test_reconciliation_rejects_custom_runtime_values_before_database_work(
    field_name: str,
    unsafe_value: object,
    message: str,
) -> None:
    reconciler = AuditReconciler(
        uow_factory=lambda: (_ for _ in ()).throw(AssertionError("no uow"))
    )

    with pytest.raises(ValueError, match=message):
        await reconciler.reconcile(
            [replace(EVENT, **{field_name: unsafe_value})],
            dry_run=False,
        )


async def test_reconciliation_archives_only_after_complete_success(tmp_path) -> None:
    fallback = JsonlAuditFallback(tmp_path / "audit-fallback.jsonl")
    fallback.append(EVENT)
    repository = _Repository([True])
    reconciler = AuditReconciler(uow_factory=lambda: _UnitOfWork(repository))

    report = await reconciler.reconcile_file(fallback, dry_run=False)

    archives = list(tmp_path.glob("audit-fallback.jsonl.reconciled-*"))
    assert report.imported == 1
    assert not fallback.path.exists()
    assert len(archives) == 1
    assert archives[0].is_file()


async def test_reconciliation_failure_leaves_source_unarchived(tmp_path) -> None:
    fallback = JsonlAuditFallback(tmp_path / "audit-fallback.jsonl")
    fallback.append(EVENT)
    reconciler = AuditReconciler(
        uow_factory=lambda: _UnitOfWork(_Repository([], error=RuntimeError("database failed")))
    )

    with pytest.raises(RuntimeError, match="database failed"):
        await reconciler.reconcile_file(fallback, dry_run=False)

    assert fallback.path.is_file()
    assert not list(tmp_path.glob("audit-fallback.jsonl.reconciled-*"))


async def test_reconciliation_cleans_the_new_archive_if_source_removal_fails(
    tmp_path,
    monkeypatch,
) -> None:
    fallback = JsonlAuditFallback(tmp_path / "audit-fallback.jsonl")
    fallback.append(EVENT)
    reconciler = AuditReconciler(uow_factory=lambda: _UnitOfWork(_Repository([True])))

    def fail_source_removal(path) -> None:
        raise PermissionError("simulated source removal failure")

    monkeypatch.setattr(audit_reconciliation, "_remove_source", fail_source_removal)

    with pytest.raises(PermissionError, match="source removal failure"):
        await reconciler.reconcile_file(fallback, dry_run=False)

    assert fallback.path.is_file()
    assert not list(tmp_path.glob("audit-fallback.jsonl.reconciled-*"))


async def test_existing_archives_do_not_block_a_new_batch(tmp_path) -> None:
    fallback = JsonlAuditFallback(tmp_path / "audit-fallback.jsonl")
    fallback.append(EVENT)
    existing = tmp_path / "audit-fallback.jsonl.reconciled-previous"
    existing.write_text("existing", encoding="utf-8")
    repository = _Repository([True])
    reconciler = AuditReconciler(uow_factory=lambda: _UnitOfWork(repository))

    report = await reconciler.reconcile_file(fallback, dry_run=False)

    assert report.imported == 1
    assert repository.events == [EVENT]
    assert not fallback.path.exists()
    assert len(list(tmp_path.glob("audit-fallback.jsonl.reconciled-*"))) == 2


async def test_reconciliation_holds_lock_through_archive_and_allows_later_append(tmp_path) -> None:
    fallback = JsonlAuditFallback(tmp_path / "audit-fallback.jsonl")
    fallback.append(EVENT)
    repository = _SourceAppendAttemptRepository(fallback)
    reconciler = AuditReconciler(uow_factory=lambda: _UnitOfWork(repository))

    report = await reconciler.reconcile_file(fallback, dry_run=False)

    assert report.imported == 1
    assert repository.events == [EVENT]
    assert repository.busy is True
    assert not fallback.path.exists()
    fallback.append(replace(EVENT, id="22222222-2222-4222-8222-222222222222"))
    assert fallback.load_events() == [
        replace(EVENT, id="22222222-2222-4222-8222-222222222222"),
    ]
    second_repository = _Repository([True])
    second_reconciler = AuditReconciler(
        uow_factory=lambda: _UnitOfWork(second_repository)
    )

    second_report = await second_reconciler.reconcile_file(fallback, dry_run=False)

    assert second_report.imported == 1
    assert len(list(tmp_path.glob("audit-fallback.jsonl.reconciled-*"))) == 2


async def test_missing_source_stops_before_any_database_import(tmp_path) -> None:
    fallback = JsonlAuditFallback(tmp_path / "does-not-exist.jsonl")
    repository = _Repository([True])
    reconciler = AuditReconciler(uow_factory=lambda: _UnitOfWork(repository))

    with pytest.raises(FileNotFoundError, match="fallback file does not exist"):
        await reconciler.reconcile_file(fallback, dry_run=False)

    assert repository.events == []
