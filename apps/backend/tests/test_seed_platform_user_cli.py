from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.platform.models import Role, User
from app.platform.persistence import DatabaseUnavailable, MigrationRequired

SCRIPT_PATH = Path(__file__).parents[3] / "scripts" / "seed_platform_user.py"


def _load_cli_module():
    specification = importlib.util.spec_from_file_location("platform_user_seed_cli", SCRIPT_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@dataclass
class _Users:
    existing: User | None = None
    added: list[User] = field(default_factory=list)

    async def get_by_username_norm(self, username_norm: str) -> User | None:
        return self.existing

    async def add(self, user: User) -> None:
        self.added.append(user)


class _UnitOfWork:
    def __init__(self, users: _Users) -> None:
        self.users = users
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class _Store:
    def __init__(self, users: _Users) -> None:
        self._users = users
        self.uow = _UnitOfWork(users)
        self.closed = False

    async def seed(self, user: User) -> bool:
        async with self.uow as uow:
            if await uow.users.get_by_username_norm(user.username_norm) is not None:
                return False
            await uow.users.add(user)
            await uow.commit()
        return True

    async def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("role", [Role.ADMIN, Role.OPERATOR, Role.VIEWER])
def test_cli_seeds_normalized_user_with_confirmed_password(
    role: Role,
    capsys,
) -> None:
    module = _load_cli_module()
    users = _Users()
    store = _Store(users)
    requested_passwords: list[str] = []

    exit_code = module.main(
        ["--username", "  Admin  ", "--display-name", "Demo Admin", "--role", role.value],
        getpass_fn=lambda prompt: (requested_passwords.append(prompt) or "correct horse battery"),
        settings_factory=lambda: type("Settings", (), {"database_url": "postgresql+psycopg://test"})(),
        store_factory=lambda database_url: store,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert requested_passwords == ["Password: ", "Confirm password: "]
    assert len(users.added) == 1
    user = users.added[0]
    assert user.username_norm == "admin"
    assert user.display_name == "Demo Admin"
    assert user.role is role
    assert user.disabled_at is None
    assert user.created_at.tzinfo is UTC
    assert user.updated_at == user.created_at
    assert user.password_hash.startswith("$argon2")
    assert "correct horse battery" not in captured.out
    assert user.password_hash not in captured.out
    assert json.loads(captured.out) == {
        "created": True,
        "username": "admin",
        "displayName": "Demo Admin",
        "role": role.value,
    }
    assert captured.err == ""
    assert store.uow.committed is True
    assert store.closed is True


def test_cli_rejects_mismatched_confirmation_before_creating_database_store(capsys) -> None:
    module = _load_cli_module()
    factory_calls: list[str] = []
    settings_calls: list[None] = []
    passwords = iter(("first-password", "second-password"))

    def unexpected_settings() -> object:
        settings_calls.append(None)
        raise AssertionError("settings must not load before password confirmation")

    exit_code = module.main(
        ["--username", "admin", "--display-name", "Demo Admin", "--role", "admin"],
        getpass_fn=lambda prompt: next(passwords),
        settings_factory=unexpected_settings,
        store_factory=lambda database_url: factory_calls.append(database_url),
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"] == {
        "code": "password_mismatch",
        "message": "Password confirmation did not match.",
    }
    assert settings_calls == []
    assert factory_calls == []
    assert "first-password" not in captured.err
    assert "second-password" not in captured.err


def test_cli_reports_unavailable_password_input_before_loading_settings_or_database(capsys) -> None:
    module = _load_cli_module()
    settings_calls: list[None] = []
    store_calls: list[str] = []

    def unavailable_password(prompt: str) -> str:
        raise EOFError("terminal password input failed")

    def unexpected_settings() -> object:
        settings_calls.append(None)
        raise AssertionError("settings must not load when password input is unavailable")

    exit_code = module.main(
        ["--username", "admin", "--display-name", "Demo Admin", "--role", "admin"],
        getpass_fn=unavailable_password,
        settings_factory=unexpected_settings,
        store_factory=lambda database_url: store_calls.append(database_url),
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"] == {
        "code": "password_input_unavailable",
        "message": "Password input is unavailable.",
    }
    assert "terminal password input failed" not in captured.err
    assert "Traceback" not in captured.err
    assert settings_calls == []
    assert store_calls == []


def test_cli_maps_unique_username_race_to_stable_error_and_closes_resources(capsys) -> None:
    module = _load_cli_module()
    password = "seed-password"
    secret_dsn = "postgresql+psycopg://seed:secret@db.example.test/platform"

    class _UniqueViolation:
        diag = type("Diagnostic", (), {"constraint_name": "uq_users_username_norm"})()

    class _RacingUsers:
        def __init__(self) -> None:
            self.added: list[User] = []

        async def get_by_username_norm(self, username_norm: str) -> User | None:
            return None

        async def add(self, user: User) -> None:
            self.added.append(user)

    class _RacingUnitOfWork:
        def __init__(self) -> None:
            self.users = _RacingUsers()
            self.rollback_count = 0
            self.closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            if exc_type is not None:
                self.rollback_count += 1
            self.closed = True

        async def commit(self) -> None:
            raise IntegrityError("INSERT", {}, _UniqueViolation())

    class _RacingStore:
        def __init__(self) -> None:
            self.uow = _RacingUnitOfWork()
            self.closed = False

        async def seed(self, user: User) -> bool:
            async with self.uow as uow:
                if await uow.users.get_by_username_norm(user.username_norm) is not None:
                    return False
                await uow.users.add(user)
                await uow.commit()
            return True

        async def close(self) -> None:
            self.closed = True

    store = _RacingStore()
    exit_code = module.main(
        ["--username", "admin", "--display-name", "Demo Admin", "--role", "admin"],
        getpass_fn=lambda prompt: password,
        settings_factory=lambda: type("Settings", (), {"database_url": secret_dsn})(),
        store_factory=lambda database_url: store,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"] == {
        "code": "username_exists",
        "message": "A platform user with this username already exists.",
    }
    assert captured.out == ""
    assert password not in captured.err
    assert store.uow.users.added[0].password_hash not in captured.err
    assert secret_dsn not in captured.err
    assert "Traceback" not in captured.err
    assert len(store.uow.users.added) == 1
    assert store.uow.rollback_count == 1
    assert store.uow.closed is True
    assert store.closed is True


def test_cli_reports_duplicate_username_without_exposing_password_or_hash(capsys) -> None:
    module = _load_cli_module()
    existing = User(
        id="11111111-1111-4111-8111-111111111111",
        username_norm="admin",
        display_name="Existing Admin",
        password_hash="$argon2id$existing-secret-hash",
        role=Role.ADMIN,
        disabled_at=None,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    store = _Store(_Users(existing=existing))

    exit_code = module.main(
        ["--username", "ADMIN", "--display-name", "Demo Admin", "--role", "admin"],
        getpass_fn=lambda prompt: "seed-password",
        settings_factory=lambda: type("Settings", (), {"database_url": "postgresql+psycopg://test"})(),
        store_factory=lambda database_url: store,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"] == {
        "code": "username_exists",
        "message": "A platform user with this username already exists.",
    }
    assert "seed-password" not in captured.err
    assert existing.password_hash not in captured.err
    assert store.uow.committed is False
    assert store.closed is True


@pytest.mark.parametrize(
    ("failure", "code", "message"),
    [
        (DatabaseUnavailable(), "database_unavailable", "The platform database is unavailable."),
        (MigrationRequired(), "migration_required", "Platform database migration is required."),
    ],
)
def test_cli_reports_database_and_migration_failures_without_dsn(
    failure: Exception,
    code: str,
    message: str,
    capsys,
) -> None:
    module = _load_cli_module()
    secret_dsn = "postgresql+psycopg://seed:secret@db.example.test/platform"

    class _FailingStore:
        async def seed(self, user: User) -> bool:
            raise failure

        async def close(self) -> None:
            return None

    exit_code = module.main(
        ["--username", "admin", "--display-name", "Demo Admin", "--role", "admin"],
        getpass_fn=lambda prompt: "seed-password",
        settings_factory=lambda: type("Settings", (), {"database_url": secret_dsn})(),
        store_factory=lambda database_url: _FailingStore(),
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"] == {"code": code, "message": message}
    assert secret_dsn not in captured.err
    assert "seed-password" not in captured.err


def test_cli_rejects_password_argument_without_echoing_its_value(capsys) -> None:
    module = _load_cli_module()
    password_argument = "--password=never-on-command-line"

    exit_code = module.main(
        [
            "--username",
            "admin",
            "--display-name",
            "Demo Admin",
            "--role",
            "admin",
            password_argument,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"]["code"] == "arguments_invalid"
    assert password_argument not in captured.err
