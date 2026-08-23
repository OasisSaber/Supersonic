"""Explicitly create one local platform user after an interactive password prompt."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from getpass import getpass
from pathlib import Path
from typing import NoReturn, Protocol
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "apps" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.postgres.database import (  # noqa: E402
    create_database_engine,
    create_session_factory,
)
from app.adapters.postgres.readiness import SqlAlchemyPlatformReadiness  # noqa: E402
from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork  # noqa: E402
from app.adapters.security import PwdlibPasswordHasher  # noqa: E402
from app.config import RuntimeSettings, load_settings  # noqa: E402
from app.platform.models import Role, User  # noqa: E402
from app.platform.persistence import DatabaseUnavailable, MigrationRequired  # noqa: E402
from app.platform.security import PasswordHasher  # noqa: E402
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # noqa: E402


class SeedCliError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise SeedCliError("arguments_invalid", "The platform user seed arguments are invalid.")


class PlatformUserStore(Protocol):
    async def seed(self, user: User) -> bool: ...

    async def close(self) -> None: ...


SettingsFactory = Callable[[], RuntimeSettings]
StoreFactory = Callable[[str], PlatformUserStore]
GetpassFunction = Callable[[str], str]


class PostgresPlatformUserStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine = create_database_engine(database_url)

    async def seed(self, user: User) -> bool:
        await SqlAlchemyPlatformReadiness(self._database_url, engine=self._engine).check()
        session_factory = create_session_factory(self._engine)
        async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
            if await uow.users.get_by_username_norm(user.username_norm) is not None:
                return False
            await uow.users.add(user)
            await uow.commit()
        return True

    async def close(self) -> None:
        await self._engine.dispose()


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = _SafeArgumentParser(description="Create one local Supersonic platform user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", required=True, choices=tuple(role.value for role in Role))
    return parser.parse_args(arguments)


def _build_user(parsed: argparse.Namespace, password: str, hasher: PasswordHasher) -> User:
    username_norm = parsed.username.strip().casefold()
    display_name = parsed.display_name.strip()
    if not username_norm or len(username_norm) > 128:
        raise SeedCliError("arguments_invalid", "The platform user seed arguments are invalid.")
    if not display_name or len(display_name) > 128:
        raise SeedCliError("arguments_invalid", "The platform user seed arguments are invalid.")
    now = datetime.now(UTC)
    return User(
        id=str(uuid4()),
        username_norm=username_norm,
        display_name=display_name,
        password_hash=hasher.hash(password),
        role=Role(parsed.role),
        disabled_at=None,
        created_at=now,
        updated_at=now,
    )


async def _seed_and_close(store: PlatformUserStore, user: User) -> bool:
    try:
        return await store.seed(user)
    finally:
        await store.close()


def main(
    arguments: Sequence[str] | None = None,
    *,
    getpass_fn: GetpassFunction = getpass,
    settings_factory: SettingsFactory = load_settings,
    store_factory: StoreFactory = PostgresPlatformUserStore,
) -> int:
    try:
        parsed = parse_args(arguments)
        password = getpass_fn("Password: ")
        confirmation = getpass_fn("Confirm password: ")
        if password != confirmation:
            raise SeedCliError("password_mismatch", "Password confirmation did not match.")
        settings = settings_factory()
        if settings.database_url is None:
            raise SeedCliError(
                "database_unconfigured",
                "A configured platform database is required to seed a platform user.",
            )
        user = _build_user(parsed, password, PwdlibPasswordHasher())
        created = asyncio.run(_seed_and_close(store_factory(settings.database_url), user))
        if not created:
            raise SeedCliError(
                "username_exists",
                "A platform user with this username already exists.",
            )
    except SeedCliError as error:
        return _write_error(error.code, error.message)
    except EOFError:
        return _write_error("password_input_unavailable", "Password input is unavailable.")
    except MigrationRequired:
        return _write_error("migration_required", "Platform database migration is required.")
    except DatabaseUnavailable:
        return _write_error("database_unavailable", "The platform database is unavailable.")
    except IntegrityError as error:
        if _is_username_conflict(error):
            return _write_error(
                "username_exists",
                "A platform user with this username already exists.",
            )
        return _write_error("database_unavailable", "The platform database is unavailable.")
    except (SQLAlchemyError, OSError, RuntimeError, ValueError):
        return _write_error("database_unavailable", "The platform database is unavailable.")
    print(
        json.dumps(
            {
                "created": True,
                "username": user.username_norm,
                "displayName": user.display_name,
                "role": user.role.value,
            },
            separators=(",", ":"),
        )
    )
    return 0


def _is_username_conflict(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None) == "uq_users_username_norm"


def _write_error(code: str, message: str) -> int:
    print(json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
