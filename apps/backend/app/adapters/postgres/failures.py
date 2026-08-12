from __future__ import annotations

from sqlalchemy.exc import InterfaceError, OperationalError, TimeoutError

from app.platform.persistence import DatabaseUnavailable

KNOWN_DATABASE_FAILURES = (OperationalError, InterfaceError, TimeoutError)


def database_unavailable(_error: BaseException) -> DatabaseUnavailable:
    """Translate a classified infrastructure failure without exposing its details."""
    return DatabaseUnavailable()
