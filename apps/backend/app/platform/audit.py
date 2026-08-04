from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from .errors import AuditUnavailable
from .models import AuditRecord


class AuditSink(Protocol):
    async def is_available(self) -> bool: ...

    async def append(self, record: AuditRecord) -> None: ...


class AuditFallback(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class AuditBuffer:
    """Bounded local fallback for safety-critical records during database outage."""

    def __init__(self, *, max_records: int = 256) -> None:
        self._max_records = max_records
        self._records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> None:
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]

    def drain(self) -> list[AuditRecord]:
        records = self._records
        self._records = []
        return records

    @property
    def records(self) -> Sequence[AuditRecord]:
        return tuple(self._records)


class JsonlAuditBuffer:
    """Durable, bounded local fallback for a later PostgreSQL reconciliation pass."""

    def __init__(self, path: Path, *, max_bytes: int = 1_048_576) -> None:
        self._path = path
        self._max_bytes = max_bytes

    def append(self, record: AuditRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.is_file() and self._path.stat().st_size >= self._max_bytes:
            rotated = self._path.with_suffix(self._path.suffix + ".1")
            rotated.unlink(missing_ok=True)
            self._path.replace(rotated)
        payload = {
            "auditId": record.audit_id,
            "occurredAt": record.occurred_at.isoformat(),
            "actorUserId": record.actor_user_id,
            "actorRole": record.actor_role.value,
            "actorSessionId": record.actor_session_id,
            "endpoint": record.endpoint,
            "commandName": record.command_name,
            "correlationId": record.correlation_id,
            "result": record.result.value,
            "parameters": record.parameters,
            "errorCode": record.error_code,
            "sourceType": record.source_type,
        }
        with self._path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    def read_payloads(self) -> list[dict]:
        if not self._path.is_file():
            return []
        payloads: list[dict] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                payloads.append(value)
        return payloads


class InMemoryAuditSink:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.records: list[AuditRecord] = []

    async def is_available(self) -> bool:
        return self.available

    async def append(self, record: AuditRecord) -> None:
        if not self.available:
            raise AuditUnavailable("Audit sink is unavailable.")
        self.records.append(record)
