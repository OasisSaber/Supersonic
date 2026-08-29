from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import Any
from uuid import UUID

from .models import AuditEvent

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwordhash",
        "passworddigest",
        "token",
        "rawtoken",
        "accesstoken",
        "refreshtoken",
        "sessiontoken",
        "authorization",
        "apikey",
        "secret",
        "rawsecret",
        "clientsecret",
        "cookie",
        "databasedsn",
        "dsn",
        "setcookie",
        "sqlerror",
    }
)
_PRIVATE_TEXT_KEYS = frozenset(
    {
        "destination",
        "destinationname",
        "instruction",
        "message",
        "prompt",
        "query",
        "roadname",
        "suggestion",
        "text",
        "userinput",
    }
)
_MAX_TEXT_LENGTH = 160
_MAX_LIST_ITEMS = 8
_MAX_DEPTH = 4
_UUID_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_AUDIT_SAFE_PARAMETER_KEYS = frozenset(
    {
        "attempt",
        "command",
        "count",
        "eventId",
        "mode",
        "newRole",
        "oldRole",
        "privacyEnabled",
        "reason",
        "revokedSessionCount",
        "state",
        "status",
        "targetUserId",
        "temperatureC",
        "theme",
    }
)
_AUDIT_REDACTED_PARAMETER_KEYS = frozenset(
    {
        "api_key",
        "database_dsn",
        "destinationName",
        "private_text",
        "raw_secret",
        "raw_token",
        "session_secret",
        "sql_error",
    }
)
_AUDIT_PARAMETER_KEY_ORDER = (
    "attempt",
    "command",
    "count",
    "eventId",
    "mode",
    "oldRole",
    "newRole",
    "privacyEnabled",
    "revokedSessionCount",
    "targetUserId",
    "reason",
    "state",
    "status",
    "temperatureC",
    "theme",
    "api_key",
    "database_dsn",
    "destinationName",
    "private_text",
    "raw_secret",
    "raw_token",
    "session_secret",
    "sql_error",
)
_AUDIT_COMMAND_VALUES = frozenset(
    {
        "acknowledge_risk",
        "confirm_route",
        "reset_session",
        "resolve_risk",
        "revoke_platform_session",
        "select_destination",
        "set_cabin_control",
        "set_media_state",
        "set_system_mode",
        "set_theme",
        "submit_trip_suggestion",
    }
)
_AUDIT_ENUM_VALUES: dict[str, frozenset[str]] = {
    "mode": frozenset({"normal", "warning", "takeover", "stale", "offline", "recovery"}),
    "newRole": frozenset({"admin", "operator", "viewer"}),
    "oldRole": frozenset({"admin", "operator", "viewer"}),
    "reason": frozenset(
        {
            "admin_revoke",
            "operator_request",
            "role_changed",
            "security_review",
            "user_disabled",
        }
    ),
    "state": frozenset({"playing", "paused", "suppressed"}),
    "status": frozenset(
        {"attempted", "succeeded", "rejected", "error", "ready", "degraded", "unavailable"}
    ),
    "theme": frozenset({"day", "night"}),
}
_AUDIT_SIMULATED_RISK_EVENT_ID = re.compile(
    r"simulated-takeover-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_AUDIT_ACTIONS = frozenset(
    {
        "auth.login",
        "auth.logout",
        "cockpit.command",
        "recovery.completed",
        "risk.detected",
        "session.revoke",
        "user.disable",
        "user.enable",
        "user.role_change",
    }
)
_AUDIT_ENDPOINTS = frozenset({"center", "cluster", "control", "hud", "overview", "passenger"})
_AUDIT_TARGET_TYPES = frozenset({"climate_zone", "platform_session", "risk_event", "user"})
_AUDIT_ERROR_CODES = frozenset(
    {
        "admin_mutation_failed",
        "audit_conflict",
        "audit_unavailable",
        "command_forbidden",
        "command_not_implemented",
        "control_disabled",
        "database_unavailable",
        "endpoint_mismatch",
        "internal_error",
        "invalid_parameters",
        "invalid_transition",
        "last_admin_protected",
        "risk_not_found",
        "role_forbidden",
        "safety_suppressed",
        "session_not_found",
        "source_mismatch",
        "user_not_found",
    }
)


def sanitize_parameters(value: Any, *, depth: int = 0) -> Any:
    """Bound audit payloads and remove secrets before persistence or logging."""
    if depth >= _MAX_DEPTH:
        return "[truncated]"
    if value is None or type(value) in {bool, int, float}:
        return value
    if type(value) is str:
        if not _safe_parameter_text(value):
            return "[redacted]"
        return value if len(value) <= _MAX_TEXT_LENGTH else value[:_MAX_TEXT_LENGTH] + "…"
    if type(value) is list:
        return [sanitize_parameters(item, depth=depth + 1) for item in value[:_MAX_LIST_ITEMS]]
    if type(value) is dict:
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:_MAX_LIST_ITEMS]:
            if type(key) is not str:
                continue
            normalized_key = _normalize_key(key)
            if _should_redact_key(normalized_key):
                result[key] = "[redacted]"
            else:
                result[key] = sanitize_parameters(item, depth=depth + 1)
        return result
    return "[redacted]"


def sanitize_audit_event(event: AuditEvent) -> AuditEvent:
    """Redact free-form metadata before an audit fact reaches durable storage."""
    return replace(
        event,
        endpoint=_sanitize_enum_metadata(event.endpoint, _AUDIT_ENDPOINTS),
        cockpit_session_id=_sanitize_uuid_metadata(event.cockpit_session_id),
        command_name=_sanitize_command_metadata(event.command_name),
        correlation_id=_sanitize_uuid_metadata(event.correlation_id),
        target_type=_sanitize_enum_metadata(event.target_type, _AUDIT_TARGET_TYPES),
        target_id=_sanitize_target_id(event.target_id),
        parameters=sanitize_audit_parameters(event.parameters),
        error_code=_sanitize_enum_metadata(event.error_code, _AUDIT_ERROR_CODES),
        source_type=_sanitize_required_enum_metadata(event.source_type, {"local_hmi"}),
        action=_sanitize_required_enum_metadata(event.action, _AUDIT_ACTIONS),
    )


def sanitize_audit_parameters(value: object) -> dict[str, Any]:
    """Keep only defined, non-sensitive AuditEvent parameter facts."""
    if type(value) is not dict:
        return {}
    exact_string_items = {key: item for key, item in value.items() if type(key) is str}
    sanitized: dict[str, Any] = {}
    for key in _AUDIT_PARAMETER_KEY_ORDER:
        if key not in exact_string_items:
            continue
        item = exact_string_items[key]
        if key in _AUDIT_REDACTED_PARAMETER_KEYS:
            sanitized[key] = "[redacted]"
            continue
        if key not in _AUDIT_SAFE_PARAMETER_KEYS:
            continue
        safe_value = _sanitize_audit_parameter_value(key, item)
        sanitized[key] = safe_value if safe_value is not None else "[redacted]"
    return sanitized


def _sanitize_audit_parameter_value(key: str, value: object) -> Any | None:
    if key == "privacyEnabled":
        return value if type(value) is bool else None
    if key in {"attempt", "count", "revokedSessionCount"}:
        return value if type(value) is int and 0 <= value <= 1_000_000 else None
    if key == "temperatureC":
        if type(value) not in {int, float}:
            return None
        return value if math.isfinite(value) and -100 <= value <= 200 else None
    if type(value) is not str:
        return None
    if key == "command":
        return value if value in _AUDIT_COMMAND_VALUES else None
    if key == "eventId":
        return _canonical_audit_identifier(value)
    if key == "targetUserId":
        return _canonical_audit_identifier(value)
    allowed = _AUDIT_ENUM_VALUES[key]
    return value if value in allowed else None


def _safe_audit_identifier(value: str) -> bool:
    return _canonical_audit_identifier(value) is not None


def _canonical_audit_identifier(value: object) -> str | None:
    if type(value) is not str:
        return None
    normalized = value.lower()
    if _UUID_TEXT.fullmatch(normalized) is not None:
        return str(UUID(value))
    if _AUDIT_SIMULATED_RISK_EVENT_ID.fullmatch(normalized) is not None:
        return normalized
    return None


def _sanitize_required_enum_metadata(value: object, allowed: frozenset[str]) -> str:
    return _sanitize_enum_metadata(value, allowed) or "[redacted]"


def _sanitize_enum_metadata(value: object, allowed: frozenset[str]) -> str | None:
    if value is None:
        return None
    return value if type(value) is str and value in allowed else "[redacted]"


def _sanitize_command_metadata(value: object) -> str | None:
    return _sanitize_enum_metadata(value, _AUDIT_COMMAND_VALUES)


def _sanitize_uuid_metadata(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _UUID_TEXT.fullmatch(value.lower()) is None:
        return "[redacted]"
    return str(UUID(value))


def _sanitize_target_id(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        return "[redacted]"
    return _canonical_audit_identifier(value) or "[redacted]"


def _looks_like_opaque_token(value: str) -> bool:
    compact = value.replace("-", "").replace("_", "").replace(".", "").replace(":", "")
    return (
        len(compact) >= 24
        and compact.isalnum()
        and len(set(compact.lower())) >= 6
        and _UUID_TEXT.fullmatch(value.lower()) is None
    )


def _contains_private_parameter_text(value: str) -> bool:
    normalized = value.lower()
    return (
        "://" in value
        or "/" in value
        or "\\" in value
        or "bearer " in normalized
        or "credential" in normalized
        or "password" in normalized
        or "secret" in normalized
        or "token" in normalized
        or "sqlstate" in normalized
        or normalized.startswith(("select ", "insert ", "update ", "delete "))
    )


def _safe_parameter_text(value: str) -> bool:
    return not _contains_private_parameter_text(value) and not _looks_like_opaque_token(value)


def _normalize_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _should_redact_key(normalized_key: str) -> bool:
    return (
        normalized_key in _SENSITIVE_KEYS
        or normalized_key in _PRIVATE_TEXT_KEYS
        or normalized_key.endswith("path")
    )
