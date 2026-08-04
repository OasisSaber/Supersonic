from __future__ import annotations

from typing import Any

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwordHash",
        "token",
        "sessionToken",
        "authorization",
        "apiKey",
        "secret",
    }
)
_SENSITIVE_KEYS_LOWER = frozenset(key.lower() for key in _SENSITIVE_KEYS)
_MAX_TEXT_LENGTH = 160
_MAX_LIST_ITEMS = 8
_MAX_DEPTH = 4


def sanitize_parameters(value: Any, *, depth: int = 0) -> Any:
    """Bound audit payloads and remove secrets before persistence or logging."""
    if depth >= _MAX_DEPTH:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= _MAX_TEXT_LENGTH else value[:_MAX_TEXT_LENGTH] + "…"
    if isinstance(value, list):
        return [sanitize_parameters(item, depth=depth + 1) for item in value[:_MAX_LIST_ITEMS]]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:_MAX_LIST_ITEMS]:
            normalized = str(key)
            if normalized.lower() in _SENSITIVE_KEYS_LOWER:
                result[normalized] = "[redacted]"
            else:
                result[normalized] = sanitize_parameters(item, depth=depth + 1)
        return result
    return str(value)[:_MAX_TEXT_LENGTH]
