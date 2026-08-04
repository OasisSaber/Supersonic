"""Backward-compatible imports for the refactored cockpit application service."""

from .cockpit import (
    DESTINATION_NAME_MAX_LENGTH,
    SUGGESTION_MAX_LENGTH,
    CockpitService,
    CommandRejected,
    navigation_data_freshness,
)


class CockpitStateAuthority(CockpitService):
    """Compatibility name retained for gp05.v1 callers and existing tests."""


__all__ = [
    "CockpitStateAuthority",
    "CommandRejected",
    "DESTINATION_NAME_MAX_LENGTH",
    "SUGGESTION_MAX_LENGTH",
    "navigation_data_freshness",
]
