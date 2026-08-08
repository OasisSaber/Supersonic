from __future__ import annotations

from typing import Any

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwordhash",
        "passworddigest",
        "token",
        "accesstoken",
        "refreshtoken",
        "sessiontoken",
        "authorization",
        "apikey",
        "secret",
        "clientsecret",
        "cookie",
        "setcookie",
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
            rendered_key = str(key)
            normalized_key = _normalize_key(rendered_key)
            if _should_redact_key(normalized_key):
                result[rendered_key] = "[redacted]"
            else:
                result[rendered_key] = sanitize_parameters(item, depth=depth + 1)
        return result
    return str(value)[:_MAX_TEXT_LENGTH]


def _normalize_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _should_redact_key(normalized_key: str) -> bool:
    return (
        normalized_key in _SENSITIVE_KEYS
        or normalized_key in _PRIVATE_TEXT_KEYS
        or normalized_key.endswith("path")
    )
