"""Shared, non-interactive PostgreSQL helpers for local recovery tooling."""

from __future__ import annotations

import hashlib
import os
import subprocess
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import psycopg
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

_REQUIRED_TABLES = ("users", "platform_sessions", "audit_events")
_CONNECTION_ENVIRONMENT_KEYS = frozenset(
    {
        option.envvar.decode("ascii")
        for option in psycopg.pq.Conninfo.get_defaults()
        if option.envvar is not None
    }
    | {
        "DATABASE_URL",
        "PGREQUIRESSL",
        "PGSERVICEFILE",
    }
)
_CONNECTION_ENVIRONMENT_LOCK = threading.RLock()
_LOCAL_HOST_ALIASES = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True, slots=True)
class PostgresConnection:
    database: str
    host: str | None
    port: int | None
    username: str | None
    password: str | None
    sslmode: str | None

    def subprocess_env(self) -> dict[str, str]:
        environment = _environment_without_connection_settings()
        environment["PGDATABASE"] = self.database
        _set_or_remove(environment, "PGHOST", self.host)
        _set_or_remove(
            environment, "PGPORT", str(self.port) if self.port is not None else None
        )
        _set_or_remove(environment, "PGUSER", self.username)
        _set_or_remove(environment, "PGPASSWORD", self.password)
        _set_or_remove(environment, "PGSSLMODE", self.sslmode)
        return environment

    def connect_kwargs(self) -> dict[str, Any]:
        values: dict[str, Any] = {"dbname": self.database}
        if self.host is not None:
            values["host"] = self.host
        if self.port is not None:
            values["port"] = self.port
        if self.username is not None:
            values["user"] = self.username
        if self.password is not None:
            values["password"] = self.password
        if self.sslmode is not None:
            values["sslmode"] = self.sslmode
        return values


def parse_database_url(raw: str) -> PostgresConnection:
    try:
        url = make_url(raw)
        port = url.port
    except (ArgumentError, AttributeError, TypeError, ValueError) as error:
        raise ValueError("The platform database URL is invalid.") from error
    if url.drivername != "postgresql+psycopg":
        raise ValueError("The platform database URL must use postgresql+psycopg.")
    if not url.database:
        raise ValueError("The platform database URL must name a database.")

    raw_sslmode = url.query.get("sslmode")
    if isinstance(raw_sslmode, tuple):
        raw_sslmode = raw_sslmode[-1] if raw_sslmode else None
    sslmode = str(raw_sslmode) if raw_sslmode is not None else None
    return PostgresConnection(
        database=url.database,
        host=url.host,
        port=port,
        username=url.username,
        password=url.password,
        sslmode=sslmode,
    )


def database_target_key(connection: PostgresConnection) -> tuple[str | None, int, str]:
    """Return a conservative physical-target key without credential material."""
    normalized_host = (
        connection.host.casefold().rstrip(".") if connection.host else "localhost"
    )
    if normalized_host in _LOCAL_HOST_ALIASES:
        normalized_host = "localhost"
    return normalized_host, connection.port or 5432, connection.database


def database_metadata(connection: PostgresConnection) -> dict[str, object]:
    with _without_connection_environment():
        raw_database = psycopg.connect(**connection.connect_kwargs())
    with raw_database as database:
        with database.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT version_num FROM alembic_version")
            revision_row = cursor.fetchone()
            if (
                revision_row is None
                or not revision_row
                or revision_row[0] is None
                or not str(revision_row[0]).strip()
            ):
                raise RuntimeError("The platform migration revision is unavailable.")
            revision = str(revision_row[0])

            row_counts: dict[str, int] = {}
            for table in _REQUIRED_TABLES:
                cursor.execute(f"SELECT count(*) FROM {table}")
                count_row = cursor.fetchone()
                if count_row is None or not count_row or count_row[0] is None:
                    raise RuntimeError(
                        "Required platform table metadata is unavailable."
                    )
                count = int(count_row[0])
                if count < 0:
                    raise RuntimeError("Required platform table metadata is invalid.")
                row_counts[table] = count

    return {
        "alembicRevision": revision,
        "rowCounts": row_counts,
    }


def database_recovery_state(connection: PostgresConnection) -> dict[str, object]:
    """Read the fixed metadata and invariants required after a controlled restore."""
    with _without_connection_environment():
        raw_database = psycopg.connect(**connection.connect_kwargs())
    with raw_database as database:
        with database.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT version_num FROM alembic_version")
            revision_row = cursor.fetchone()
            if (
                revision_row is None
                or not revision_row
                or revision_row[0] is None
                or not str(revision_row[0]).strip()
            ):
                raise RuntimeError(
                    "The restored platform migration revision is unavailable."
                )
            revision = str(revision_row[0])

            row_counts: dict[str, int] = {}
            for table in _REQUIRED_TABLES:
                cursor.execute(f"SELECT count(*) FROM {table}")
                row_counts[table] = _required_nonnegative_count(cursor.fetchone())

            cursor.execute(
                "SELECT count(*) FROM users WHERE role = 'admin' AND disabled_at IS NULL"
            )
            enabled_admin_count = _required_nonnegative_count(cursor.fetchone())
            cursor.execute(
                "SELECT count(*) FROM users AS u "
                "JOIN platform_sessions AS s ON s.user_id = u.id "
                "WHERE u.disabled_at IS NOT NULL AND s.revoked_at IS NULL "
                "AND s.expires_at > CURRENT_TIMESTAMP"
            )
            disabled_user_active_session_count = _required_nonnegative_count(
                cursor.fetchone()
            )
            cursor.execute(
                "SELECT count(*) FROM platform_sessions "
                "WHERE revoke_reason IS NOT NULL AND revoked_at IS NULL"
            )
            orphan_revoke_reason_count = _required_nonnegative_count(cursor.fetchone())

    return {
        "alembicRevision": revision,
        "rowCounts": row_counts,
        "invariants": {
            "enabledAdminCount": enabled_admin_count,
            "disabledUserActiveSessionCount": disabled_user_active_session_count,
            "orphanRevokeReasonCount": orphan_revoke_reason_count,
        },
    }


def _required_nonnegative_count(row: object) -> int:
    if not isinstance(row, tuple) or not row or row[0] is None:
        raise RuntimeError("Required platform recovery metadata is unavailable.")
    value = row[0]
    if isinstance(value, bool):
        raise RuntimeError("Required platform recovery metadata is invalid.")
    count = int(value)
    if count < 0:
        raise RuntimeError("Required platform recovery metadata is invalid.")
    return count


def run_postgres_tool(
    executable: str,
    arguments: list[str],
    connection: PostgresConnection,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [executable, *arguments],
        env=connection.subprocess_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def tool_version(executable: str) -> str:
    result = subprocess.run(
        [executable, "--version"],
        env=_environment_without_connection_settings(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("The required PostgreSQL tool is unavailable.")
    version = result.stdout.strip()
    if not version:
        raise RuntimeError("The required PostgreSQL tool version is unavailable.")
    return version


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _environment_without_connection_settings() -> dict[str, str]:
    environment = os.environ.copy()
    for key in _CONNECTION_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    return environment


@contextmanager
def _without_connection_environment() -> Iterator[None]:
    with _CONNECTION_ENVIRONMENT_LOCK:
        preserved = {
            key: os.environ[key]
            for key in _CONNECTION_ENVIRONMENT_KEYS
            if key in os.environ
        }
        for key in _CONNECTION_ENVIRONMENT_KEYS:
            os.environ.pop(key, None)
        try:
            yield
        finally:
            for key in _CONNECTION_ENVIRONMENT_KEYS:
                os.environ.pop(key, None)
            os.environ.update(preserved)


def _set_or_remove(environment: dict[str, str], key: str, value: str | None) -> None:
    if value is None:
        environment.pop(key, None)
    else:
        environment[key] = value
