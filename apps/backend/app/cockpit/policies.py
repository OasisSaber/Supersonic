from __future__ import annotations

from enum import Enum
from typing import TypeVar

from ..contracts.v1 import (
    ENDPOINT_COMMAND_PERMISSIONS,
    CommandEnvelopeV1,
    CommandName,
    EndpointId,
)
from .errors import CommandRejected

EnumT = TypeVar("EnumT", bound=Enum)

IMPLEMENTED_COMMANDS = frozenset(
    {
        CommandName.SET_THEME,
        CommandName.SET_SYSTEM_MODE,
        CommandName.SELECT_DESTINATION,
        CommandName.CONFIRM_ROUTE,
        CommandName.ACKNOWLEDGE_RISK,
        CommandName.RESOLVE_RISK,
        CommandName.SET_MEDIA_STATE,
        CommandName.SUBMIT_TRIP_SUGGESTION,
        CommandName.SET_CABIN_CONTROL,
        CommandName.RESET_SESSION,
    }
)


class CommandPolicy:
    """Validate transport claims against server-owned endpoint context."""

    def validate(
        self,
        command: CommandEnvelopeV1,
        *,
        server_endpoint: EndpointId | None,
    ) -> None:
        endpoint = server_endpoint or command.payload.endpoint
        if command.payload.endpoint != endpoint:
            raise CommandRejected(
                "endpoint_mismatch",
                "Declared endpoint must match the server-owned endpoint context.",
                status_code=403,
            )
        if command.source.kind != "endpoint" or command.source.id != endpoint.value:
            raise CommandRejected(
                "source_mismatch",
                "Command source must match the server-owned endpoint.",
                status_code=403,
            )
        if command.payload.name not in ENDPOINT_COMMAND_PERMISSIONS[endpoint]:
            raise CommandRejected(
                "command_forbidden",
                f"Endpoint {endpoint.value} cannot issue {command.payload.name.value}.",
                status_code=403,
            )
        if command.payload.name not in IMPLEMENTED_COMMANDS:
            raise CommandRejected(
                "command_not_implemented",
                f"Command {command.payload.name.value} is reserved but not implemented.",
                status_code=501,
            )


class Parameters:
    """Exact, typed command-parameter reader with consistent error semantics."""

    def __init__(self, raw: dict) -> None:
        self._raw = raw

    def require_exact(self, *keys: str) -> None:
        expected = set(keys)
        if set(self._raw) != expected:
            expected_text = ", ".join(sorted(expected)) or "no parameters"
            raise CommandRejected(
                "invalid_parameters",
                f"Command requires exactly: {expected_text}.",
            )

    def text(self, key: str, *, max_length: int, label: str | None = None) -> str:
        value = self._raw.get(key)
        field_name = label or key
        if not isinstance(value, str) or not value.strip():
            raise CommandRejected(
                "invalid_parameters",
                f"{field_name} must be a non-empty string.",
            )
        normalized = value.strip()
        if len(normalized) > max_length:
            raise CommandRejected(
                "invalid_parameters",
                f"{field_name} must be at most {max_length} characters.",
            )
        return normalized

    def boolean(self, key: str, *, label: str | None = None) -> bool:
        value = self._raw.get(key)
        field_name = label or key
        if not isinstance(value, bool):
            raise CommandRejected(
                "invalid_parameters",
                f"{field_name} must be boolean.",
            )
        return value

    def enum(self, key: str, enum_type: type[EnumT], *, message: str) -> EnumT:
        try:
            return enum_type(self._raw.get(key))
        except (TypeError, ValueError) as exc:
            raise CommandRejected("invalid_parameters", message) from exc
