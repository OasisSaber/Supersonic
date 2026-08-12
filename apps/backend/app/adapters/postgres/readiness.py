from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import InterfaceError as PsycopgInterfaceError
from psycopg import OperationalError as PsycopgOperationalError
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.platform.persistence import (
    DatabaseUnavailable,
    MigrationRequired,
    PlatformReadiness,
    PlatformReadinessPort,
)

from .database import create_database_engine
from .failures import KNOWN_DATABASE_FAILURES, database_unavailable

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


class SqlAlchemyPlatformReadiness(PlatformReadinessPort):
    def __init__(self, database_url: str | None, *, engine: AsyncEngine | None = None) -> None:
        self._database_url = database_url
        self._engine = engine

    async def check(self) -> PlatformReadiness:
        if not self._database_url:
            raise DatabaseUnavailable
        try:
            current_heads = await self._read_current_heads()
        except (
            *KNOWN_DATABASE_FAILURES,
            PsycopgInterfaceError,
            PsycopgOperationalError,
        ) as exc:
            raise database_unavailable(exc) from exc
        if current_heads is None or current_heads != self._expected_heads():
            raise MigrationRequired
        return PlatformReadiness.READY

    def _expected_heads(self) -> set[str]:
        configuration = Config(str(_BACKEND_ROOT / "alembic.ini"))
        return set(ScriptDirectory.from_config(configuration).get_heads())

    async def _read_current_heads(self) -> set[str] | None:
        engine = self._engine or create_database_engine(self._database_url or "")
        try:
            async with engine.connect() as connection:
                try:
                    result = await connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    )
                except ProgrammingError as exc:
                    if _is_missing_version_table(exc):
                        return None
                    raise
                return {str(value) for value in result.scalars()}
        finally:
            if self._engine is None:
                await engine.dispose()


def _is_missing_version_table(error: ProgrammingError) -> bool:
    original = error.orig
    sqlstate = getattr(original, "sqlstate", None)
    if sqlstate is None:
        diagnostic = getattr(original, "diag", None)
        sqlstate = getattr(diagnostic, "sqlstate", None)
    return sqlstate == "42P01"
