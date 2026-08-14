from __future__ import annotations

import json
import math
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, TypeVar, cast
from uuid import UUID

from .audit_validation import validate_audit_event_runtime_types
from .models import AuditDelivery, AuditEvent, AuditResult, Role
from .sanitization import sanitize_audit_event, sanitize_audit_parameters

_SCHEMA_VERSION = 1
_DEFAULT_MAX_BYTES = 1_048_576
_MAX_PARAMETER_ITEMS = 8
_ALLOWED_KEYS = frozenset(
    {
        "schemaVersion",
        "id",
        "occurredAt",
        "action",
        "result",
        "delivery",
        "actorUserId",
        "actorPlatformSessionId",
        "actorRole",
        "endpoint",
        "cockpitSessionId",
        "commandName",
        "correlationId",
        "targetType",
        "targetId",
        "parameters",
        "errorCode",
        "sourceType",
    }
)
_REQUIRED_KEYS = frozenset(
    _ALLOWED_KEYS
)
_AuditEnum = TypeVar("_AuditEnum", AuditResult, AuditDelivery, Role)
_LOCAL_LOCKS_GUARD = threading.Lock()
_LOCAL_LOCKS: dict[Path, threading.Lock] = {}


class AuditFallbackError(RuntimeError):
    """A JSONL fallback cannot safely retain or read an audit fact."""


class AuditFallbackFull(AuditFallbackError):
    pass


class AuditFallbackFormatError(AuditFallbackError):
    pass


class AuditFallbackBusy(AuditFallbackError):
    pass


class JsonlAuditFallback:
    """Strict, bounded local storage for sanitized events pending reconciliation."""

    def __init__(self, path: Path, *, max_bytes: int = _DEFAULT_MAX_BYTES) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be at least 1")
        self._path = path
        self._max_bytes = max_bytes

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: AuditEvent) -> AuditEvent:
        fallback_event = _fallback_event(event)
        line = _encode_event(fallback_event)
        incoming_size = len(line.encode("utf-8"))
        with self.locked():
            current_size = self._path.stat().st_size if self._path.is_file() else 0
            if current_size + incoming_size > self._max_bytes:
                raise AuditFallbackFull("Audit fallback reached its maximum size.")
            self._append_line(line)
        return fallback_event

    def load_events(self) -> list[AuditEvent]:
        with self.locked():
            events, _ = self.load_events_with_fingerprint_locked()
        return events

    def load_events_with_fingerprint(self) -> tuple[list[AuditEvent], str]:
        with self.locked():
            return self.load_events_with_fingerprint_locked()

    def load_events_with_fingerprint_locked(self) -> tuple[list[AuditEvent], str]:
        """Read a stable source while the caller owns this fallback's lock."""
        if not self._path.is_file():
            return [], sha256(b"").hexdigest()
        source = self._read_source()
        try:
            text = source.decode("utf-8")
        except UnicodeDecodeError as error:
            raise AuditFallbackFormatError("Audit fallback must be valid UTF-8.") from error
        events: list[AuditEvent] = []
        for line_number, line in enumerate(
            text.splitlines(),
            start=1,
        ):
            if not line:
                raise AuditFallbackFormatError(
                    f"Audit fallback line {line_number} must not be empty."
            )
            events.append(_decode_event(line, line_number))
        return events, sha256(source).hexdigest()

    def matches_fingerprint(self, fingerprint: str) -> bool:
        with self.locked():
            return self.matches_fingerprint_locked(fingerprint)

    def matches_fingerprint_locked(self, fingerprint: str) -> bool:
        """Check the source while the caller owns this fallback's lock."""
        if not self._path.is_file():
            return False
        return sha256(self._read_source()).hexdigest() == fingerprint

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Acquire the cooperative append/reconciliation lock without blocking."""
        self._create_parent_if_needed()
        local_lock = _local_lock_for(self._path)
        if not local_lock.acquire(blocking=False):
            raise AuditFallbackBusy("Audit fallback is busy.")
        descriptor: int | None = None
        descriptor_locked = False
        try:
            descriptor = self._open_lock_descriptor()
            try:
                _lock_descriptor(descriptor)
            except OSError as error:
                raise AuditFallbackBusy("Audit fallback is busy.") from error
            descriptor_locked = True
            yield
        finally:
            try:
                if descriptor is not None and descriptor_locked:
                    _unlock_descriptor(descriptor)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                local_lock.release()

    def _create_parent_if_needed(self) -> None:
        missing: list[Path] = []
        parent = self._path.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            directory.mkdir(mode=0o700, exist_ok=True)
            if os.name != "nt":
                directory.chmod(0o700)

    def _open_lock_descriptor(self) -> int:
        lock_path = self._path.with_name(f"{self._path.name}.lock")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        return descriptor

    def _read_source(self) -> bytes:
        if self._path.stat().st_size > self._max_bytes:
            raise AuditFallbackFull("Audit fallback reached its maximum size.")
        source = self._path.read_bytes()
        if len(source) > self._max_bytes:
            raise AuditFallbackFull("Audit fallback reached its maximum size.")
        return source

    def _append_line(self, line: str) -> None:
        descriptor = os.open(
            self._path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)


def _local_lock_for(path: Path) -> threading.Lock:
    resolved = path.resolve()
    with _LOCAL_LOCKS_GUARD:
        return _LOCAL_LOCKS.setdefault(resolved, threading.Lock())


def _lock_descriptor(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_descriptor(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)


def _fallback_event(event: AuditEvent) -> AuditEvent:
    _validate_persistable_event(event)
    sanitized = sanitize_audit_event(event)
    parameters = sanitized.parameters
    if not isinstance(parameters, dict):
        raise AuditFallbackFormatError("Audit parameters must sanitize to an object.")
    return replace(
        sanitized,
        delivery=AuditDelivery.FALLBACK,
        parameters=cast(dict[str, Any], parameters),
    )


def _encode_event(event: AuditEvent) -> str:
    payload: dict[str, object] = {
        "schemaVersion": _SCHEMA_VERSION,
        "id": event.id,
        "occurredAt": event.occurred_at.isoformat(),
        "action": event.action,
        "result": event.result.value,
        "delivery": event.delivery.value,
        "actorUserId": event.actor_user_id,
        "actorPlatformSessionId": event.actor_platform_session_id,
        "actorRole": event.actor_role.value if event.actor_role is not None else None,
        "endpoint": event.endpoint,
        "cockpitSessionId": event.cockpit_session_id,
        "commandName": event.command_name,
        "correlationId": event.correlation_id,
        "targetType": event.target_type,
        "targetId": event.target_id,
        "parameters": event.parameters,
        "errorCode": event.error_code,
        "sourceType": event.source_type,
    }
    try:
        return (
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        )
    except (TypeError, ValueError) as error:
        raise AuditFallbackFormatError(
            "Audit event parameters must be JSON-compatible."
        ) from error


def _decode_event(line: str, line_number: int) -> AuditEvent:
    try:
        value = json.loads(line, parse_constant=_reject_nonstandard_json_constant)
    except (json.JSONDecodeError, ValueError) as error:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} is not valid JSON."
        ) from error
    if not isinstance(value, dict):
        raise AuditFallbackFormatError(f"Audit fallback line {line_number} must be an object.")
    if set(value) - _ALLOWED_KEYS or _REQUIRED_KEYS - set(value):
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} has an unexpected field set."
        )
    if (
        type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != _SCHEMA_VERSION
    ):
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} has an unsupported schema version."
        )
    return _event_from_payload(value, line_number)


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"Nonstandard JSON constant: {value}")


def _event_from_payload(payload: dict[str, object], line_number: int) -> AuditEvent:
    event_id = _uuid_value(payload["id"], "id", line_number)
    occurred_at = _datetime_value(payload["occurredAt"], line_number)
    action = _nonempty_string(payload["action"], "action", line_number)
    result = _enum_value(AuditResult, payload["result"], "result", line_number)
    delivery = _enum_value(AuditDelivery, payload["delivery"], "delivery", line_number)
    parameters = payload["parameters"]
    if not isinstance(parameters, dict):
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} parameters must be an object."
        )
    event = AuditEvent(
        id=event_id,
        occurred_at=occurred_at,
        action=action,
        result=result,
        delivery=delivery,
        actor_user_id=_optional_uuid_value(payload.get("actorUserId"), "actorUserId", line_number),
        actor_platform_session_id=_optional_uuid_value(
            payload.get("actorPlatformSessionId"),
            "actorPlatformSessionId",
            line_number,
        ),
        actor_role=_optional_enum_value(Role, payload.get("actorRole"), "actorRole", line_number),
        endpoint=_optional_string(payload.get("endpoint"), "endpoint", line_number),
        cockpit_session_id=_optional_string(
            payload.get("cockpitSessionId"),
            "cockpitSessionId",
            line_number,
        ),
        command_name=_optional_string(payload.get("commandName"), "commandName", line_number),
        correlation_id=_optional_string(payload.get("correlationId"), "correlationId", line_number),
        target_type=_optional_string(payload.get("targetType"), "targetType", line_number),
        target_id=_optional_string(payload.get("targetId"), "targetId", line_number),
        parameters=_sanitized_parameters(parameters, line_number),
        error_code=_optional_string(payload.get("errorCode"), "errorCode", line_number),
        source_type=_nonempty_string(payload["sourceType"], "sourceType", line_number),
    )
    _validate_persistable_event(event)
    sanitized = sanitize_audit_event(event)
    if event.delivery is not AuditDelivery.FALLBACK:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} delivery must be fallback."
        )
    return sanitized


def _validate_persistable_event(event: AuditEvent) -> None:
    try:
        validate_audit_event_runtime_types(event)
    except ValueError as error:
        raise AuditFallbackFormatError(str(error)) from error
    try:
        UUID(event.id)
    except (AttributeError, TypeError, ValueError) as error:
        raise AuditFallbackFormatError("Audit event id must be a valid UUID.") from error
    if event.occurred_at.tzinfo is None or event.occurred_at.utcoffset() is None:
        raise AuditFallbackFormatError("Audit event occurred_at must be timezone-aware.")
    if event.result is AuditResult.DEGRADED:
        raise AuditFallbackFormatError("AuditResult.DEGRADED is not persistable.")
    if event.delivery is AuditDelivery.LOST:
        raise AuditFallbackFormatError("AuditDelivery.LOST has no persistence medium.")
    _validate_required_string(event.action, "action", maximum_length=128)
    _validate_required_string(event.source_type, "source_type", maximum_length=32)
    _validate_optional_string_length(event.endpoint, "endpoint", maximum_length=32)
    _validate_optional_string_length(
        event.cockpit_session_id,
        "cockpit_session_id",
        maximum_length=80,
    )
    _validate_optional_string_length(
        event.command_name,
        "command_name",
        maximum_length=64,
    )
    _validate_optional_string_length(
        event.correlation_id,
        "correlation_id",
        maximum_length=64,
    )
    _validate_optional_string_length(
        event.target_type,
        "target_type",
        maximum_length=64,
    )
    _validate_optional_string_length(
        event.target_id,
        "target_id",
        maximum_length=128,
    )
    _validate_optional_string_length(
        event.error_code,
        "error_code",
        maximum_length=64,
    )
    _validate_optional_uuid(event.actor_user_id, "actor_user_id")
    _validate_optional_uuid(
        event.actor_platform_session_id,
        "actor_platform_session_id",
    )
    _reject_nonfinite_parameters(event.parameters)


def _reject_nonfinite_parameters(value: object, *, depth: int = 0) -> None:
    if depth >= 4:
        return
    if type(value) is float and not math.isfinite(value):
        raise AuditFallbackFormatError("Audit event parameters must be JSON-compatible.")
    if type(value) is list:
        for item in value[:_MAX_PARAMETER_ITEMS]:
            _reject_nonfinite_parameters(item, depth=depth + 1)
    if type(value) is dict:
        for item in list(value.values())[:_MAX_PARAMETER_ITEMS]:
            _reject_nonfinite_parameters(item, depth=depth + 1)


def _validate_optional_uuid(value: str | None, name: str) -> None:
    if value is None:
        return
    if type(value) is not str:
        raise AuditFallbackFormatError(f"Audit event {name} must be a valid UUID.")
    try:
        UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise AuditFallbackFormatError(
            f"Audit event {name} must be a valid UUID."
        ) from error


def _validate_required_string(
    value: object,
    name: str,
    *,
    maximum_length: int,
) -> None:
    if type(value) is not str or not value:
        raise AuditFallbackFormatError(
            f"Audit event {name} must be a non-empty string."
        )
    _validate_string_length(value, name, maximum_length=maximum_length)


def _validate_optional_string_length(
    value: str | None,
    name: str,
    *,
    maximum_length: int,
) -> None:
    if value is None:
        return
    if type(value) is not str or not value:
        raise AuditFallbackFormatError(
            f"Audit event {name} must be a non-empty string when supplied."
        )
    _validate_string_length(value, name, maximum_length=maximum_length)


def _validate_string_length(value: str, name: str, *, maximum_length: int) -> None:
    if len(value) > maximum_length:
        raise AuditFallbackFormatError(
            f"Audit event {name} must be at most {maximum_length} characters."
        )


def _sanitized_parameters(
    parameters: dict[str, object],
    line_number: int,
) -> dict[str, Any]:
    return cast(dict[str, Any], sanitize_audit_parameters(parameters))


def _uuid_value(value: object, name: str, line_number: int) -> str:
    if type(value) is not str:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} {name} must be a UUID string."
        )
    try:
        return str(UUID(value))
    except ValueError as error:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} {name} must be a UUID string."
        ) from error


def _optional_uuid_value(value: object, name: str, line_number: int) -> str | None:
    if value is None:
        return None
    return _uuid_value(value, name, line_number)


def _datetime_value(value: object, line_number: int) -> datetime:
    if type(value) is not str:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} occurredAt must be an ISO timestamp."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} occurredAt must be an ISO timestamp."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} occurredAt must be timezone-aware."
        )
    return parsed.astimezone(UTC)


def _nonempty_string(value: object, name: str, line_number: int) -> str:
    if type(value) is not str or not value:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} {name} must be a non-empty string."
        )
    return value


def _optional_string(value: object, name: str, line_number: int) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, name, line_number)


def _enum_value(
    enum_type: type[_AuditEnum],
    value: object,
    name: str,
    line_number: int,
) -> _AuditEnum:
    if type(value) is not str:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} {name} is invalid."
        )
    try:
        return enum_type(value)
    except ValueError as error:
        raise AuditFallbackFormatError(
            f"Audit fallback line {line_number} {name} is invalid."
        ) from error


def _optional_enum_value(
    enum_type: type[_AuditEnum],
    value: object,
    name: str,
    line_number: int,
) -> _AuditEnum | None:
    if value is None:
        return None
    return _enum_value(enum_type, value, name, line_number)
