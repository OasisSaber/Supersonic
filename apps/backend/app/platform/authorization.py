from __future__ import annotations

from ..contracts.v1 import CommandName
from .errors import RoleForbidden
from .models import Principal, Role

_OPERATOR_COMMANDS = frozenset(
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
    }
)


class RoleCommandPolicy:
    """Apply platform role rules in addition to existing endpoint permissions."""

    def authorize(self, principal: Principal, command_name: CommandName) -> None:
        if principal.role is Role.ADMIN:
            return
        if principal.role is Role.OPERATOR and command_name in _OPERATOR_COMMANDS:
            return
        if principal.role is Role.VIEWER:
            raise RoleForbidden("Viewer sessions are read-only.")
        raise RoleForbidden()
