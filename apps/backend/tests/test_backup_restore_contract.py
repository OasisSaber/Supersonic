from __future__ import annotations

import hashlib
import importlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
TOOLS_PATH = SCRIPTS_ROOT / "platform_db_tools.py"
BACKUP_PATH = SCRIPTS_ROOT / "platform_backup.py"
RESTORE_PATH = SCRIPTS_ROOT / "platform_restore.py"
MANIFEST_KEYS = {
    "formatVersion",
    "createdAt",
    "databaseName",
    "alembicRevision",
    "rowCounts",
    "dumpSha256",
    "pgDumpVersion",
}
REQUIRED_TABLES = {"users", "platform_sessions", "audit_events"}
DATABASE_URL = (
    "postgresql+psycopg://backup-user:p%40ss%3Aword@db.example.test:6543/supersonic?sslmode=require"
)
PASSWORD = "p@ss:word"
DUMP_BYTES = b"PGDMP\x01controlled-test-dump"
RESTORE_DATABASE_URL = (
    "postgresql+psycopg://restore-user:r%40store%3Aword@127.0.0.1:5432/"
    "supersonic_restore_test?sslmode=require"
)
RESTORE_PASSWORD = "r@store:word"
REPOSITORY_HEAD = "20260809_0001"


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS_ROOT))
    sys.modules.pop("platform_backup", None)
    sys.modules.pop("platform_db_tools", None)
    tools = importlib.import_module("platform_db_tools")
    backup = importlib.import_module("platform_backup")
    return tools, backup


@pytest.fixture
def restore_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS_ROOT))
    sys.modules.pop("platform_restore", None)
    sys.modules.pop("platform_db_tools", None)
    tools = importlib.import_module("platform_db_tools")
    restore = importlib.import_module("platform_restore")
    return tools, restore


def _manifest_path(output: Path) -> Path:
    return output.with_suffix(output.suffix + ".manifest.json")


def _owned_path(value) -> Path:
    return Path(getattr(value, "path", value))


def _completed(returncode: int = 0, *, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["pg_dump"], returncode, stdout="", stderr=stderr)


def _install_success_dependencies(monkeypatch, backup, *, dump_bytes: bytes = DUMP_BYTES):
    calls: dict[str, object] = {}
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)

    def version(executable: str) -> str:
        calls["version"] = executable
        return "pg_dump (PostgreSQL) 18.4"

    def run(executable: str, arguments: list[str], connection):
        calls["tool"] = (executable, list(arguments), connection)
        temp_path = Path(arguments[arguments.index("--file") + 1])
        calls["dump_temp"] = temp_path
        assert temp_path.exists()
        temp_path.write_bytes(dump_bytes)
        return _completed()

    def metadata(connection):
        calls["metadata_connection"] = connection
        return {
            "alembicRevision": "20260821_slice_e",
            "rowCounts": {
                "users": 3,
                "platform_sessions": 5,
                "audit_events": 42,
                "untrusted_extra": 999,
            },
            "untrustedMetadata": PASSWORD,
        }

    monkeypatch.setattr(backup, "tool_version", version)
    monkeypatch.setattr(backup, "run_postgres_tool", run)
    monkeypatch.setattr(backup, "database_metadata", metadata)
    monkeypatch.setattr(
        backup,
        "_utc_now",
        lambda: datetime(2026, 8, 21, 10, 0, tzinfo=timezone(timedelta(hours=8))),
    )
    return calls


def _assert_no_owned_outputs(output: Path) -> None:
    assert not output.exists()
    assert not _manifest_path(output).exists()
    assert list(output.parent.glob(f".{output.name}.*.tmp")) == []
    assert list(output.parent.glob(f".{_manifest_path(output).name}.*.tmp")) == []


def _restore_manifest(*, dump_bytes: bytes = DUMP_BYTES) -> dict[str, object]:
    return {
        "formatVersion": 1,
        "createdAt": "2026-08-21T02:00:00Z",
        "databaseName": "supersonic",
        "alembicRevision": REPOSITORY_HEAD,
        "rowCounts": {
            "users": 3,
            "platform_sessions": 5,
            "audit_events": 42,
        },
        "dumpSha256": hashlib.sha256(dump_bytes).hexdigest(),
        "pgDumpVersion": "pg_dump (PostgreSQL) 18.4",
    }


def _write_restore_inputs(tmp_path: Path) -> tuple[Path, Path]:
    dump = tmp_path / "platform.dump"
    manifest = _manifest_path(dump)
    dump.write_bytes(DUMP_BYTES)
    manifest.write_text(json.dumps(_restore_manifest()), encoding="utf-8")
    return dump, manifest


def _install_restore_success(monkeypatch, restore, tmp_path: Path):
    dump, manifest = _write_restore_inputs(tmp_path)
    calls: dict[str, object] = {}
    monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", "1")
    monkeypatch.setenv("RESTORE_DATABASE_URL", RESTORE_DATABASE_URL)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://source-user:source-secret@127.0.0.1:5432/supersonic",
    )
    monkeypatch.setattr(restore, "_repository_heads", lambda: [REPOSITORY_HEAD])

    def run(executable: str, arguments: list[str], connection):
        calls["tool"] = (executable, list(arguments), connection)
        return subprocess.CompletedProcess(
            [executable, *arguments],
            0,
            stdout="",
            stderr="",
        )

    def verify(connection):
        calls["verification_connection"] = connection
        return {
            "alembicRevision": REPOSITORY_HEAD,
            "rowCounts": {
                "users": 3,
                "platform_sessions": 5,
                "audit_events": 42,
            },
            "invariants": {
                "enabledAdminCount": 1,
                "disabledUserActiveSessionCount": 0,
                "orphanRevokeReasonCount": 0,
            },
        }

    monkeypatch.setattr(restore, "run_postgres_tool", run)
    monkeypatch.setattr(restore, "database_recovery_state", verify)
    return dump, manifest, calls


def test_production_backup_modules_exist() -> None:
    assert TOOLS_PATH.is_file()
    assert BACKUP_PATH.is_file()
    assert RESTORE_PATH.is_file()


def test_parse_database_url_decodes_fields_and_builds_connect_kwargs(modules) -> None:
    tools, _ = modules

    connection = tools.parse_database_url(DATABASE_URL)

    assert connection.database == "supersonic"
    assert connection.host == "db.example.test"
    assert connection.port == 6543
    assert connection.username == "backup-user"
    assert connection.password == PASSWORD
    assert connection.sslmode == "require"
    assert connection.connect_kwargs() == {
        "dbname": "supersonic",
        "host": "db.example.test",
        "port": 6543,
        "user": "backup-user",
        "password": PASSWORD,
        "sslmode": "require",
    }


@pytest.mark.parametrize(
    "raw_url",
    [
        "postgresql://backup:secret@localhost/supersonic",
        "sqlite:///supersonic.db",
        "://not-a-database-url",
        "postgresql+psycopg://backup:secret@localhost",
        "postgresql+psycopg://backup:secret@localhost/",
    ],
)
def test_parse_database_url_rejects_wrong_driver_or_missing_database(modules, raw_url: str) -> None:
    tools, _ = modules

    with pytest.raises(ValueError):
        tools.parse_database_url(raw_url)


def test_subprocess_environment_sets_explicit_fields_and_removes_redirectors(
    modules,
    monkeypatch,
) -> None:
    tools, _ = modules
    inherited = {
        "DATABASE_URL": "postgresql+psycopg://inherited:wrong@elsewhere/other",
        "PGHOST": "wrong-host",
        "PGHOSTADDR": "203.0.113.5",
        "PGPORT": "9999",
        "PGUSER": "wrong-user",
        "PGPASSWORD": "wrong-password",
        "PGDATABASE": "wrong-database",
        "PGSSLMODE": "disable",
        "PGSERVICE": "redirecting-service",
        "PGSERVICEFILE": "secret-service-file",
        "PGPASSFILE": "secret-password-file",
        "UNRELATED_SETTING": "preserved",
    }
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)
    connection = tools.parse_database_url("postgresql+psycopg:///supersonic")

    environment = connection.subprocess_env()

    assert environment["PGDATABASE"] == "supersonic"
    assert environment["UNRELATED_SETTING"] == "preserved"
    for key in (
        "DATABASE_URL",
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGUSER",
        "PGPASSWORD",
        "PGSSLMODE",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGPASSFILE",
    ):
        assert key not in environment


def test_pg_dump_receives_secret_only_in_sanitized_environment(modules, monkeypatch) -> None:
    tools, _ = modules
    observed: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed.update(kwargs)
        return _completed()

    monkeypatch.setattr(tools.subprocess, "run", fake_run)
    connection = tools.parse_database_url(DATABASE_URL)

    result = tools.run_postgres_tool(
        "pg_dump",
        ["--format=custom", "--file", "safe.dump"],
        connection,
    )

    assert result.returncode == 0
    assert observed["argv"] == [
        "pg_dump",
        "--format=custom",
        "--file",
        "safe.dump",
    ]
    assert PASSWORD not in " ".join(observed["argv"])
    assert DATABASE_URL not in " ".join(observed["argv"])
    environment = observed["env"]
    assert environment["PGPASSWORD"] == PASSWORD
    assert environment["PGHOST"] == "db.example.test"
    assert environment["PGPORT"] == "6543"
    assert environment["PGUSER"] == "backup-user"
    assert environment["PGDATABASE"] == "supersonic"
    assert environment["PGSSLMODE"] == "require"
    assert "DATABASE_URL" not in environment
    assert observed["text"] is True
    assert observed["stdout"] is subprocess.PIPE
    assert observed["stderr"] is subprocess.PIPE
    assert observed["check"] is False


def test_tool_version_uses_exact_call_without_connection_secrets(modules, monkeypatch) -> None:
    tools, _ = modules
    observed: dict[str, object] = {}
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("PGPASSWORD", PASSWORD)
    monkeypatch.setenv("PGSERVICE", "redirecting-service")

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="pg_dump (PostgreSQL) 18.4\n", stderr="")

    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    assert tools.tool_version("pg_dump") == "pg_dump (PostgreSQL) 18.4"
    assert observed["argv"] == ["pg_dump", "--version"]
    assert "DATABASE_URL" not in observed["env"]
    assert "PGPASSWORD" not in observed["env"]
    assert "PGSERVICE" not in observed["env"]


def test_tool_version_failure_never_includes_tool_stderr(modules, monkeypatch) -> None:
    tools, _ = modules

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr=DATABASE_URL)

    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as raised:
        tools.tool_version("pg_dump")
    assert DATABASE_URL not in str(raised.value)
    assert PASSWORD not in str(raised.value)


def test_database_metadata_uses_one_read_only_transaction_and_fixed_tables(
    modules,
    monkeypatch,
) -> None:
    tools, _ = modules
    executed: list[str] = []
    connect_kwargs: dict[str, object] = {}
    rows = iter(
        [
            ("20260821_slice_e",),
            (3,),
            (5,),
            (42,),
        ]
    )

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def execute(self, statement: str) -> None:
            executed.append(statement)

        def fetchone(self):
            return next(rows)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            executed.append("CONNECTION_EXIT")
            return None

        def cursor(self):
            return Cursor()

    def connect(**kwargs):
        connect_kwargs.update(kwargs)
        return Connection()

    monkeypatch.setattr(tools.psycopg, "connect", connect)

    metadata = tools.database_metadata(tools.parse_database_url(DATABASE_URL))

    assert metadata == {
        "alembicRevision": "20260821_slice_e",
        "rowCounts": {"users": 3, "platform_sessions": 5, "audit_events": 42},
    }
    assert connect_kwargs == {
        "dbname": "supersonic",
        "host": "db.example.test",
        "port": 6543,
        "user": "backup-user",
        "password": PASSWORD,
        "sslmode": "require",
    }
    assert executed == [
        "SET TRANSACTION READ ONLY",
        "SELECT version_num FROM alembic_version",
        "SELECT count(*) FROM users",
        "SELECT count(*) FROM platform_sessions",
        "SELECT count(*) FROM audit_events",
        "CONNECTION_EXIT",
    ]


@pytest.mark.parametrize("revision", [None, (None,), ("",), ("   ",)])
def test_database_metadata_requires_non_empty_alembic_revision(
    modules,
    monkeypatch,
    revision,
) -> None:
    tools, _ = modules

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def execute(self, statement: str) -> None:
            return None

        def fetchone(self):
            return revision

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(tools.psycopg, "connect", lambda **kwargs: Connection())

    with pytest.raises(RuntimeError):
        tools.database_metadata(tools.parse_database_url(DATABASE_URL))


def test_database_metadata_sanitizes_libpq_environment_during_connect_and_restores_it(
    modules,
    monkeypatch,
) -> None:
    tools, _ = modules
    inherited = {
        "PGHOST": "redirect.example.test",
        "PGHOSTADDR": "203.0.113.7",
        "PGPORT": "7777",
        "PGUSER": "redirect-user",
        "PGPASSWORD": "redirect-password",
        "PGDATABASE": "redirect-database",
        "PGSSLMODE": "disable",
        "PGSERVICE": "redirect-service",
        "PGSERVICEFILE": "redirect-service-file",
        "PGPASSFILE": "redirect-password-file",
        "PGOPTIONS": "-c search_path=redirected",
        "PGREQUIRESSL": "1",
    }
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)
    observed_during_connect: dict[str, str] = {}
    rows = iter([("revision",), (1,), (2,), (3,)])

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def execute(self, statement: str) -> None:
            return None

        def fetchone(self):
            return next(rows)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def cursor(self):
            return Cursor()

    def connect(**kwargs):
        observed_during_connect.update(os.environ)
        return Connection()

    monkeypatch.setattr(tools.psycopg, "connect", connect)
    connection = tools.parse_database_url("postgresql+psycopg:///supersonic")

    tools.database_metadata(connection)

    for key, value in inherited.items():
        assert key not in observed_during_connect
        assert os.environ[key] == value


def test_database_metadata_restores_environment_when_connect_fails(modules, monkeypatch) -> None:
    tools, _ = modules
    inherited = {
        "PGHOST": "redirect.example.test",
        "PGSERVICE": "redirect-service",
        "PGSERVICEFILE": "redirect-service-file",
        "PGPASSFILE": "redirect-password-file",
    }
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)
    observed_during_connect: dict[str, str] = {}

    def connect(**kwargs):
        observed_during_connect.update(os.environ)
        raise RuntimeError("connection failed")

    monkeypatch.setattr(tools.psycopg, "connect", connect)

    with pytest.raises(RuntimeError):
        tools.database_metadata(tools.parse_database_url("postgresql+psycopg:///supersonic"))

    for key, value in inherited.items():
        assert key not in observed_during_connect
        assert os.environ[key] == value


def test_database_metadata_treats_missing_required_count_as_failure(modules, monkeypatch) -> None:
    tools, _ = modules
    rows = iter([("revision",), None])

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def execute(self, statement: str) -> None:
            return None

        def fetchone(self):
            return next(rows)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(tools.psycopg, "connect", lambda **kwargs: Connection())

    with pytest.raises(RuntimeError):
        tools.database_metadata(tools.parse_database_url(DATABASE_URL))


def test_sha256_file_hashes_exact_bytes(modules, tmp_path: Path) -> None:
    tools, _ = modules
    dump = tmp_path / "platform.dump"
    dump.write_bytes(DUMP_BYTES)

    assert tools.sha256_file(dump) == hashlib.sha256(DUMP_BYTES).hexdigest()


def test_backup_success_uses_exact_flags_secure_unique_temps_and_exact_manifest(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "backups" / "platform.dump"
    calls = _install_success_dependencies(monkeypatch, backup)
    real_link = os.link
    publications: list[tuple[Path, Path]] = []
    fsync_calls: list[int] = []
    real_fsync = os.fsync

    def link(source, destination, **kwargs):
        publications.append((Path(source), Path(destination)))
        real_link(source, destination, **kwargs)

    def fsync(file_descriptor: int) -> None:
        fsync_calls.append(file_descriptor)
        real_fsync(file_descriptor)

    monkeypatch.setattr(backup.os, "link", link)
    monkeypatch.setattr(backup.os, "fsync", fsync)

    returned = backup.create_backup(output)

    expected_hash = hashlib.sha256(DUMP_BYTES).hexdigest()
    expected_manifest = {
        "formatVersion": 1,
        "createdAt": "2026-08-21T02:00:00Z",
        "databaseName": "supersonic",
        "alembicRevision": "20260821_slice_e",
        "rowCounts": {"users": 3, "platform_sessions": 5, "audit_events": 42},
        "dumpSha256": expected_hash,
        "pgDumpVersion": "pg_dump (PostgreSQL) 18.4",
    }
    assert returned == expected_manifest
    assert output.read_bytes() == DUMP_BYTES
    manifest_path = _manifest_path(output)
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == expected_manifest
    assert set(expected_manifest) == MANIFEST_KEYS
    assert set(expected_manifest["rowCounts"]) == REQUIRED_TABLES
    assert len(expected_hash) == 64
    assert expected_hash == expected_hash.lower()
    assert calls["version"] == "pg_dump"
    executable, arguments, connection = calls["tool"]
    assert executable == "pg_dump"
    dump_temp = Path(calls["dump_temp"])
    assert arguments == [
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file",
        str(dump_temp),
    ]
    assert connection.password == PASSWORD
    assert dump_temp.parent == output.parent
    assert dump_temp != output.with_suffix(output.suffix + ".tmp")
    assert dump_temp.name.startswith(f".{output.name}.")
    assert len(publications) == 2
    assert publications[0] == (dump_temp, output)
    assert publications[1][0].parent == output.parent
    assert publications[1][1] == manifest_path
    assert publications[1][0].name.startswith(f".{manifest_path.name}.")
    assert len(fsync_calls) == 1
    if os.name != "nt":
        assert stat.S_IMODE(output.stat().st_mode) & 0o077 == 0


def test_backup_releases_every_owned_temp_anchor_after_success(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    created = []
    real_create = backup._create_owned_temp

    def record_owned_temp(destination):
        owned = real_create(destination)
        created.append(owned)
        return owned

    monkeypatch.setattr(backup, "_create_owned_temp", record_owned_temp)

    backup.create_backup(output)

    assert len(created) == 2
    assert all(owned.anchor is None or owned.anchor.descriptor is None for owned in created)


@pytest.mark.parametrize("existing", ["dump", "manifest"])
def test_backup_refuses_existing_final_before_pg_dump(
    modules,
    monkeypatch,
    tmp_path: Path,
    existing: str,
) -> None:
    _, backup = modules
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    output = tmp_path / "platform.dump"
    existing_path = output if existing == "dump" else _manifest_path(output)
    existing_path.write_bytes(b"foreign-final")
    calls: list[str] = []
    monkeypatch.setattr(backup, "tool_version", lambda executable: calls.append(executable))

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    assert calls == []
    assert existing_path.read_bytes() == b"foreign-final"


@pytest.mark.parametrize("existing", ["dump", "manifest"])
def test_backup_refuses_dangling_final_symlink_before_pg_dump(
    modules,
    monkeypatch,
    tmp_path: Path,
    existing: str,
) -> None:
    _, backup = modules
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    output = tmp_path / "platform.dump"
    existing_path = output if existing == "dump" else _manifest_path(output)
    missing_target = tmp_path / f"missing-{existing}"
    try:
        existing_path.symlink_to(missing_target)
    except OSError as error:
        pytest.skip(f"file symlinks are unavailable: {error}")
    calls: list[str] = []
    monkeypatch.setattr(
        backup,
        "tool_version",
        lambda executable: calls.append(executable) or "pg_dump 18.4",
    )
    monkeypatch.setattr(
        backup,
        "run_postgres_tool",
        lambda executable, arguments, connection: pytest.fail(
            "pg_dump must not run when a dangling final symlink exists"
        ),
    )

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    assert calls == []
    assert os.path.lexists(existing_path)
    assert existing_path.is_symlink()


def test_atomic_dump_publication_refuses_concurrent_final_without_overwrite(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    real_link = os.link
    real_replace = os.replace
    injected = False

    def inject_before_publish(operation, source, destination, **kwargs):
        nonlocal injected
        destination = Path(destination)
        if destination == output and not injected:
            destination.write_bytes(b"foreign-concurrent-dump")
            injected = True
        return operation(source, destination, **kwargs)

    monkeypatch.setattr(
        backup.os,
        "link",
        lambda source, destination, **kwargs: inject_before_publish(
            real_link, source, destination, **kwargs
        ),
    )
    monkeypatch.setattr(
        backup.os,
        "replace",
        lambda source, destination: inject_before_publish(real_replace, source, destination),
    )

    with pytest.raises((FileExistsError, RuntimeError)):
        backup.create_backup(output)

    assert output.read_bytes() == b"foreign-concurrent-dump"
    assert not _manifest_path(output).exists()


def test_atomic_manifest_publication_preserves_concurrent_manifest_and_removes_owned_dump(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    manifest_path = _manifest_path(output)
    _install_success_dependencies(monkeypatch, backup)
    real_link = os.link
    real_replace = os.replace
    injected = False

    def inject_before_publish(operation, source, destination, **kwargs):
        nonlocal injected
        destination = Path(destination)
        if destination == manifest_path and not injected:
            destination.write_bytes(b"foreign-concurrent-manifest")
            injected = True
        return operation(source, destination, **kwargs)

    monkeypatch.setattr(
        backup.os,
        "link",
        lambda source, destination, **kwargs: inject_before_publish(
            real_link, source, destination, **kwargs
        ),
    )
    monkeypatch.setattr(
        backup.os,
        "replace",
        lambda source, destination: inject_before_publish(real_replace, source, destination),
    )

    with pytest.raises((FileExistsError, RuntimeError)):
        backup.create_backup(output)

    assert not output.exists()
    assert manifest_path.read_bytes() == b"foreign-concurrent-manifest"


@pytest.mark.parametrize("dump_state", ["missing", "empty"])
def test_backup_rejects_missing_or_empty_dump_after_success_exit(
    modules,
    monkeypatch,
    tmp_path: Path,
    dump_state: str,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setattr(backup, "tool_version", lambda executable: "pg_dump 18.4")

    def run(executable, arguments, connection):
        temp = Path(arguments[arguments.index("--file") + 1])
        if dump_state == "missing":
            temp.unlink()
        return _completed()

    monkeypatch.setattr(backup, "run_postgres_tool", run)
    monkeypatch.setattr(
        backup,
        "database_metadata",
        lambda connection: pytest.fail("metadata must not run for a missing or empty dump"),
    )

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    _assert_no_owned_outputs(output)


def test_backup_rejects_replaced_dump_temp_inode_without_deleting_foreign_file(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    replaced_temp: Path | None = None

    def replace_dump_inode(executable, arguments, connection):
        nonlocal replaced_temp
        replaced_temp = Path(arguments[arguments.index("--file") + 1])
        replaced_temp.unlink()
        replaced_temp.write_bytes(b"foreign-replaced-temp")
        return _completed()

    monkeypatch.setattr(backup, "run_postgres_tool", replace_dump_inode)

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    assert replaced_temp is not None
    assert replaced_temp.read_bytes() == b"foreign-replaced-temp"
    assert not output.exists()
    assert not _manifest_path(output).exists()
    replaced_temp.unlink()


def test_backup_rejects_dump_temp_symlink_without_following_or_deleting_it(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    symlink_temp: Path | None = None
    foreign_target = tmp_path / "foreign-dump-target"
    foreign_target.write_bytes(b"foreign-dump-target-bytes")

    def replace_dump_with_symlink(executable, arguments, connection):
        nonlocal symlink_temp
        symlink_temp = Path(arguments[arguments.index("--file") + 1])
        symlink_temp.unlink()
        try:
            symlink_temp.symlink_to(foreign_target)
        except OSError as error:
            pytest.skip(f"file symlinks are unavailable: {error}")
        return _completed()

    monkeypatch.setattr(backup, "run_postgres_tool", replace_dump_with_symlink)

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    assert symlink_temp is not None
    assert symlink_temp.is_symlink()
    assert foreign_target.read_bytes() == b"foreign-dump-target-bytes"
    assert not output.exists()
    assert not _manifest_path(output).exists()
    symlink_temp.unlink()


def test_manifest_temp_symlink_is_rejected_without_writing_foreign_target(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    real_write_manifest = backup._write_manifest
    foreign_target = tmp_path / "foreign-manifest-target"
    foreign_target.write_bytes(b"foreign-manifest-target-bytes")
    replaced_temp: Path | None = None

    def replace_manifest_with_symlink(owned, manifest):
        nonlocal replaced_temp
        replaced_temp = _owned_path(owned)
        replaced_temp.unlink()
        try:
            replaced_temp.symlink_to(foreign_target)
        except OSError as error:
            pytest.skip(f"file symlinks are unavailable: {error}")
        return real_write_manifest(owned, manifest)

    monkeypatch.setattr(backup, "_write_manifest", replace_manifest_with_symlink)

    with pytest.raises((OSError, RuntimeError)):
        backup.create_backup(output)

    assert replaced_temp is not None
    assert replaced_temp.is_symlink()
    assert foreign_target.read_bytes() == b"foreign-manifest-target-bytes"
    assert not output.exists()
    assert not _manifest_path(output).exists()
    replaced_temp.unlink()


def test_publish_rejects_source_temp_replaced_after_hash_without_deleting_foreign_file(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    real_publish = backup._publish_no_replace
    replaced_source: Path | None = None

    def replace_before_publish(source, destination):
        nonlocal replaced_source
        if Path(destination) == output and replaced_source is None:
            replaced_source = _owned_path(source)
            replaced_source.unlink()
            replaced_source.write_bytes(b"foreign-after-hash")
        return real_publish(source, destination)

    monkeypatch.setattr(backup, "_publish_no_replace", replace_before_publish)

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    assert replaced_source is not None
    assert replaced_source.read_bytes() == b"foreign-after-hash"
    assert not output.exists()
    assert not _manifest_path(output).exists()
    replaced_source.unlink()


@pytest.mark.parametrize(
    "failure_stage",
    ["version", "pg_dump", "metadata", "hash", "serialization", "manifest_fsync", "dump_publish"],
)
def test_backup_failure_removes_only_owned_temps_and_never_leaves_final_pair(
    modules,
    monkeypatch,
    tmp_path: Path,
    failure_stage: str,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    foreign_dump_tmp = output.with_suffix(output.suffix + ".tmp")
    foreign_manifest_tmp = _manifest_path(output).with_suffix(".json.tmp")
    foreign_dump_tmp.write_bytes(b"foreign-dump-temp")
    foreign_manifest_tmp.write_bytes(b"foreign-manifest-temp")
    calls = _install_success_dependencies(monkeypatch, backup)

    if failure_stage == "version":
        monkeypatch.setattr(
            backup,
            "tool_version",
            lambda executable: (_ for _ in ()).throw(OSError()),
        )
    elif failure_stage == "pg_dump":

        def failed_dump(executable, arguments, connection):
            temp = Path(arguments[arguments.index("--file") + 1])
            temp.write_bytes(b"partial")
            return _completed(1, stderr=DATABASE_URL)

        monkeypatch.setattr(backup, "run_postgres_tool", failed_dump)
    elif failure_stage == "metadata":
        monkeypatch.setattr(
            backup,
            "database_metadata",
            lambda connection: (_ for _ in ()).throw(RuntimeError(DATABASE_URL)),
        )
    elif failure_stage == "hash":
        monkeypatch.setattr(
            backup,
            "sha256_file",
            lambda path: (_ for _ in ()).throw(OSError(DATABASE_URL)),
        )
    elif failure_stage == "serialization":
        monkeypatch.setattr(
            backup,
            "database_metadata",
            lambda connection: {
                "alembicRevision": object(),
                "rowCounts": {"users": 3, "platform_sessions": 5, "audit_events": 42},
            },
        )
    elif failure_stage == "manifest_fsync":
        monkeypatch.setattr(
            backup.os,
            "fsync",
            lambda descriptor: (_ for _ in ()).throw(OSError(DATABASE_URL)),
        )
    elif failure_stage == "dump_publish":
        monkeypatch.setattr(
            backup.os,
            "link",
            lambda source, destination: (_ for _ in ()).throw(OSError(DATABASE_URL)),
        )

    with pytest.raises((OSError, RuntimeError, TypeError)):
        backup.create_backup(output)

    _assert_no_owned_outputs(output)
    assert foreign_dump_tmp.read_bytes() == b"foreign-dump-temp"
    assert foreign_manifest_tmp.read_bytes() == b"foreign-manifest-temp"
    assert calls.get("dump_temp") != foreign_dump_tmp


def test_manifest_publication_failure_removes_newly_published_dump(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    real_link = os.link
    publication_count = 0

    def fail_second_link(source, destination, **kwargs):
        nonlocal publication_count
        publication_count += 1
        if publication_count == 2:
            raise OSError(DATABASE_URL)
        real_link(source, destination, **kwargs)

    monkeypatch.setattr(backup.os, "link", fail_second_link)

    with pytest.raises((OSError, RuntimeError)):
        backup.create_backup(output)

    assert publication_count == 2
    _assert_no_owned_outputs(output)


def test_manifest_publish_failure_prioritizes_removing_published_dump_when_temp_cleanup_fails(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    real_link = os.link
    real_unlink = Path.unlink
    manifest_temp: Path | None = None
    publication_count = 0

    def fail_second_link(source, destination, **kwargs):
        nonlocal manifest_temp, publication_count
        publication_count += 1
        if publication_count == 2:
            manifest_temp = Path(source)
            raise OSError("manifest publication failed")
        real_link(source, destination, **kwargs)

    def fail_manifest_temp_cleanup(path: Path, missing_ok: bool = False):
        if manifest_temp is not None and path == manifest_temp:
            raise OSError("manifest temp cleanup failed")
        return real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(backup.os, "link", fail_second_link)
    monkeypatch.setattr(Path, "unlink", fail_manifest_temp_cleanup)

    with pytest.raises((OSError, RuntimeError)):
        backup.create_backup(output)

    assert not output.exists()
    assert not _manifest_path(output).exists()
    if manifest_temp is not None:
        real_unlink(manifest_temp, missing_ok=True)


def test_post_claim_dump_replacement_is_detected_and_foreign_entry_is_preserved(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    real_link = os.link
    replaced = False

    def link_then_replace(source, destination, **kwargs):
        nonlocal replaced
        real_link(source, destination, **kwargs)
        destination = Path(destination)
        if destination == output and not replaced:
            destination.unlink()
            destination.write_bytes(b"foreign-post-claim")
            replaced = True

    monkeypatch.setattr(backup.os, "link", link_then_replace)

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    assert output.read_bytes() == b"foreign-post-claim"
    assert not _manifest_path(output).exists()


def test_cleanup_detects_published_dump_replacement_and_preserves_foreign_entry(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    manifest_path = _manifest_path(output)
    _install_success_dependencies(monkeypatch, backup)
    real_link = os.link
    real_remove = backup._remove_published_if_owned
    link_count = 0
    cleanup_replaced = False

    def fail_manifest_link(source, destination, **kwargs):
        nonlocal link_count
        link_count += 1
        if link_count == 2:
            raise OSError("manifest claim failed")
        real_link(source, destination, **kwargs)

    def replace_before_cleanup(path, identity):
        nonlocal cleanup_replaced
        path = Path(path)
        if path == output and not cleanup_replaced:
            path.unlink()
            path.write_bytes(b"foreign-during-cleanup")
            cleanup_replaced = True
        return real_remove(path, identity)

    monkeypatch.setattr(backup.os, "link", fail_manifest_link)
    monkeypatch.setattr(backup, "_remove_published_if_owned", replace_before_cleanup)

    with pytest.raises((OSError, RuntimeError)):
        backup.create_backup(output)

    assert output.read_bytes() == b"foreign-during-cleanup"
    assert not manifest_path.exists()


def test_published_dump_checksum_is_verified_before_manifest_claim(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)
    real_link = os.link
    modified = False

    def link_then_modify_same_inode(source, destination, **kwargs):
        nonlocal modified
        real_link(source, destination, **kwargs)
        destination = Path(destination)
        if destination == output and not modified:
            destination.write_bytes(b"same-inode-post-claim-modification")
            modified = True

    monkeypatch.setattr(backup.os, "link", link_then_modify_same_inode)

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    assert not output.exists()
    assert not _manifest_path(output).exists()


def test_published_dump_checksum_is_verified_again_before_success_return(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    manifest_path = _manifest_path(output)
    _install_success_dependencies(monkeypatch, backup)
    real_link = os.link

    def modify_dump_after_manifest_claim(source, destination, **kwargs):
        real_link(source, destination, **kwargs)
        if Path(destination) == manifest_path:
            output.write_bytes(b"same-inode-post-manifest-modification")

    monkeypatch.setattr(backup.os, "link", modify_dump_after_manifest_claim)

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    assert not output.exists()
    assert not manifest_path.exists()


def test_backup_never_reuses_or_deletes_predictable_foreign_temp_files(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    predictable_dump = output.with_suffix(output.suffix + ".tmp")
    predictable_manifest = _manifest_path(output).with_suffix(".json.tmp")
    predictable_dump.write_bytes(b"foreign dump temp")
    predictable_manifest.write_bytes(b"foreign manifest temp")
    calls = _install_success_dependencies(monkeypatch, backup)

    backup.create_backup(output)

    assert calls["dump_temp"] != predictable_dump
    assert predictable_dump.read_bytes() == b"foreign dump temp"
    assert predictable_manifest.read_bytes() == b"foreign manifest temp"


def test_owned_temp_removes_created_path_when_restrictive_setup_fails(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    destination = tmp_path / "platform.dump"
    real_mkstemp = tempfile.mkstemp
    created_path: Path | None = None

    def capture_mkstemp(**kwargs):
        nonlocal created_path
        descriptor, raw_path = real_mkstemp(**kwargs)
        created_path = Path(raw_path)
        return descriptor, raw_path

    monkeypatch.setattr(backup.tempfile, "mkstemp", capture_mkstemp)
    monkeypatch.setattr(
        backup.os,
        "fchmod",
        lambda descriptor, mode: (_ for _ in ()).throw(OSError("fchmod failed")),
        raising=False,
    )

    with pytest.raises(OSError):
        backup._create_owned_temp(destination)

    assert created_path is not None
    assert not created_path.exists()


def test_owned_temp_closes_descriptor_and_removes_path_when_initial_fstat_fails(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    destination = tmp_path / "platform.dump"
    real_mkstemp = tempfile.mkstemp
    real_fstat = os.fstat
    created_descriptor: int | None = None
    created_path: Path | None = None

    def capture_mkstemp(**kwargs):
        nonlocal created_descriptor, created_path
        descriptor, raw_path = real_mkstemp(**kwargs)
        created_descriptor = descriptor
        created_path = Path(raw_path)
        return descriptor, raw_path

    monkeypatch.setattr(backup.tempfile, "mkstemp", capture_mkstemp)
    monkeypatch.setattr(
        backup.os,
        "fstat",
        lambda descriptor: (_ for _ in ()).throw(OSError("fstat failed")),
    )

    with pytest.raises(OSError, match="fstat failed"):
        backup._create_owned_temp(destination)

    assert created_descriptor is not None
    with pytest.raises(OSError):
        real_fstat(created_descriptor)
    assert created_path is not None
    assert not created_path.exists()


def test_owned_temp_removes_created_path_when_close_fails(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    destination = tmp_path / "platform.dump"
    real_mkstemp = tempfile.mkstemp
    real_close = os.close
    created_path: Path | None = None
    close_calls = 0

    def capture_mkstemp(**kwargs):
        nonlocal created_path
        descriptor, raw_path = real_mkstemp(**kwargs)
        created_path = Path(raw_path)
        return descriptor, raw_path

    def close_then_fail(descriptor: int) -> None:
        nonlocal close_calls
        close_calls += 1
        if close_calls == 1:
            real_close(descriptor)
            raise OSError("close failed")
        real_close(descriptor)

    monkeypatch.setattr(backup.tempfile, "mkstemp", capture_mkstemp)
    monkeypatch.setattr(backup.os, "close", close_then_fail)

    with pytest.raises(OSError):
        backup._create_owned_temp(destination)

    assert created_path is not None
    assert not created_path.exists()


def test_cli_help_truthfully_requires_maintenance_window(modules, capsys) -> None:
    _, backup = modules

    with pytest.raises(SystemExit) as raised:
        backup.main(["--help"])

    captured = capsys.readouterr()
    assert raised.value.code == 0
    help_text = " ".join(captured.out.casefold().split())
    assert "maintenance window" in help_text
    assert "stop platform writers" in help_text
    assert "trusted operator-owned output directory" in help_text
    assert "exclusive cooperative access" in help_text
    assert "does not protect against malicious same-user mutation" in help_text


def test_existing_per_output_operation_lock_refuses_before_pg_dump(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    lock_path = output.with_name(f".{output.name}.backup.lock")
    lock_path.write_bytes(b"foreign-operation-lock")
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    calls: list[str] = []
    monkeypatch.setattr(
        backup,
        "tool_version",
        lambda executable: calls.append(executable) or "pg_dump 18.4",
    )
    monkeypatch.setattr(
        backup,
        "run_postgres_tool",
        lambda executable, arguments, connection: pytest.fail(
            "pg_dump must not run while the per-output operation lock exists"
        ),
    )

    with pytest.raises(RuntimeError):
        backup.create_backup(output)

    assert calls == []
    assert lock_path.read_bytes() == b"foreign-operation-lock"


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permissions only")
def test_posix_group_or_world_writable_output_directory_is_refused_before_pg_dump(
    modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, backup = modules
    output_directory = tmp_path / "unsafe-output"
    output_directory.mkdir(mode=0o700)
    output_directory.chmod(0o777)
    output = output_directory / "platform.dump"
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    calls: list[str] = []
    monkeypatch.setattr(
        backup,
        "tool_version",
        lambda executable: calls.append(executable) or "pg_dump 18.4",
    )
    try:
        with pytest.raises(RuntimeError):
            backup.create_backup(output)
    finally:
        output_directory.chmod(0o700)

    assert calls == []


def test_cli_success_is_sanitized_json(modules, monkeypatch, tmp_path: Path, capsys) -> None:
    _, backup = modules
    output = tmp_path / "platform.dump"
    _install_success_dependencies(monkeypatch, backup)

    exit_code = backup.main(["--output", str(output)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "result": "ok",
        "databaseName": "supersonic",
        "alembicRevision": "20260821_slice_e",
        "dumpSha256": hashlib.sha256(DUMP_BYTES).hexdigest(),
    }
    for secret in (DATABASE_URL, PASSWORD, "db.example.test", "backup-user"):
        assert secret not in captured.out


@pytest.mark.parametrize(
    "raised",
    [
        RuntimeError(DATABASE_URL),
        OSError(f"host=db.example.test user=backup-user password={PASSWORD}"),
        ValueError(PASSWORD),
    ],
)
def test_cli_failure_is_stable_sanitized_json_without_success_or_traceback(
    modules,
    monkeypatch,
    tmp_path: Path,
    capsys,
    raised: Exception,
) -> None:
    _, backup = modules
    monkeypatch.setattr(backup, "create_backup", lambda output: (_ for _ in ()).throw(raised))

    exit_code = backup.main(["--output", str(tmp_path / "platform.dump")])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": "backup_failed",
            "message": "Platform backup failed.",
        }
    }
    for secret in (DATABASE_URL, PASSWORD, "db.example.test", "backup-user", "Traceback"):
        assert secret not in captured.err
    assert "result" not in captured.err


def test_cli_missing_database_url_is_sanitized_and_has_no_traceback(
    modules,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _, backup = modules
    monkeypatch.delenv("DATABASE_URL", raising=False)

    exit_code = backup.main(["--output", str(tmp_path / "platform.dump")])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "backup_failed"
    assert "Traceback" not in captured.err


def test_gitignore_protects_real_backup_outputs_without_hiding_evidence_templates() -> None:
    patterns = {
        line.strip()
        for line in (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "backups/" in patterns
    assert "*.dump" in patterns
    assert "*.json" not in patterns
    assert "*.manifest.json" not in patterns


@pytest.mark.parametrize("opt_in", [None, "", "0", "true", "01", " 1"])
def test_restore_requires_exact_opt_in_before_url_files_tool_or_database(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    opt_in: str | None,
) -> None:
    _, restore = restore_modules
    if opt_in is None:
        monkeypatch.delenv("SUPERSONIC_ALLOW_DB_RESTORE", raising=False)
    else:
        monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", opt_in)
    monkeypatch.setenv("RESTORE_DATABASE_URL", RESTORE_DATABASE_URL)
    monkeypatch.setattr(
        restore,
        "parse_database_url",
        lambda raw: pytest.fail("the URL must not be parsed before exact restore opt-in"),
    )
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not run without exact opt-in"),
    )
    monkeypatch.setattr(
        restore,
        "database_recovery_state",
        lambda connection: pytest.fail("the database must not be accessed without opt-in"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(tmp_path / "missing.dump", tmp_path / "missing.manifest.json")


def test_restore_requires_url_before_files_tool_or_database(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, restore = restore_modules
    monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", "1")
    monkeypatch.delenv("RESTORE_DATABASE_URL", raising=False)
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not run without a target URL"),
    )
    monkeypatch.setattr(
        restore,
        "database_recovery_state",
        lambda connection: pytest.fail("the database must not be accessed without a target URL"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(tmp_path / "missing.dump", tmp_path / "missing.manifest.json")


@pytest.mark.parametrize(
    "restore_url",
    [
        "://invalid",
        "postgresql://restore:secret@localhost/supersonic_restore_test",
        "postgresql+psycopg://restore:secret@localhost/supersonic",
        "postgresql+psycopg://restore:secret@localhost/restore_test_extra",
    ],
)
def test_restore_rejects_invalid_or_nonisolated_target_before_files_and_tool(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    restore_url: str,
) -> None:
    _, restore = restore_modules
    monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", "1")
    monkeypatch.setenv("RESTORE_DATABASE_URL", restore_url)
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not run for an invalid target"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(tmp_path / "missing.dump", tmp_path / "missing.manifest.json")


@pytest.mark.parametrize(
    ("source_url", "target_url"),
    [
        (
            "postgresql+psycopg://source:a@localhost/supersonic_restore_test",
            "postgresql+psycopg://restore:b@127.0.0.1:5432/supersonic_restore_test",
        ),
        (
            "postgresql+psycopg://source:a@[::1]:5432/supersonic_restore_test",
            "postgresql+psycopg://restore:b@localhost/supersonic_restore_test",
        ),
        (
            "postgresql+psycopg://source:a@db.example.test:5432/supersonic_restore_test",
            "postgresql+psycopg://restore:b@DB.EXAMPLE.TEST/supersonic_restore_test",
        ),
        (
            "postgresql+psycopg:///supersonic_restore_test",
            "postgresql+psycopg://restore:b@localhost:5432/supersonic_restore_test",
        ),
        (
            "postgresql+psycopg://source:a@[::1]/supersonic_restore_test",
            "postgresql+psycopg:///supersonic_restore_test",
        ),
    ],
)
def test_restore_rejects_normalized_source_target_equality_before_files_and_tool(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    source_url: str,
    target_url: str,
) -> None:
    _, restore = restore_modules
    monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", "1")
    monkeypatch.setenv("DATABASE_URL", source_url)
    monkeypatch.setenv("RESTORE_DATABASE_URL", target_url)
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not run against the source"),
    )
    monkeypatch.setattr(
        restore,
        "_absolute_input_path",
        lambda path: pytest.fail("source/target equality must reject before file work"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(tmp_path / "missing.dump", tmp_path / "missing.manifest.json")


@pytest.mark.parametrize(
    "encoded_database_name",
    [
        "host%3Dattacker_restore_test",
        "user%3Dattacker_restore_test",
        "postgresql%3A%2F%2Fattacker_restore_test",
        "unsafe%20name_restore_test",
        "-leading_dash_restore_test",
        "unsafe%40host_restore_test",
    ],
)
def test_restore_rejects_conninfo_or_metacharacter_database_name_before_files_and_tool(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    encoded_database_name: str,
) -> None:
    _, restore = restore_modules
    monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", "1")
    monkeypatch.setenv(
        "RESTORE_DATABASE_URL",
        f"postgresql+psycopg://restore:secret@localhost/{encoded_database_name}",
    )
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not receive an unsafe dbname"),
    )
    monkeypatch.setattr(
        restore,
        "database_recovery_state",
        lambda connection: pytest.fail("an unsafe dbname must not reach database access"),
    )
    monkeypatch.setattr(
        restore,
        "_absolute_input_path",
        lambda path: pytest.fail("an unsafe dbname must reject before file work"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(tmp_path / "missing.dump", tmp_path / "missing.manifest.json")


@pytest.mark.parametrize("unsafe_input", ["missing", "directory"])
def test_restore_rejects_missing_or_nonregular_inputs_before_tool_and_database(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    unsafe_input: str,
) -> None:
    _, restore = restore_modules
    dump, manifest = _write_restore_inputs(tmp_path)
    if unsafe_input == "missing":
        dump.unlink()
    else:
        manifest.unlink()
        manifest.mkdir()
    monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", "1")
    monkeypatch.setenv("RESTORE_DATABASE_URL", RESTORE_DATABASE_URL)
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not run for unsafe inputs"),
    )
    monkeypatch.setattr(
        restore,
        "database_recovery_state",
        lambda connection: pytest.fail("the database must not be accessed for unsafe inputs"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(dump, manifest)


@pytest.mark.parametrize("input_name", ["dump", "manifest"])
def test_restore_rejects_input_symlinks_without_following_them(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    input_name: str,
) -> None:
    _, restore = restore_modules
    dump, manifest = _write_restore_inputs(tmp_path)
    path = dump if input_name == "dump" else manifest
    target = tmp_path / f"foreign-{input_name}"
    target.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(target)
    except OSError as error:
        pytest.skip(f"file symlinks are unavailable: {error}")
    monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", "1")
    monkeypatch.setenv("RESTORE_DATABASE_URL", RESTORE_DATABASE_URL)
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not follow input symlinks"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(dump, manifest)

    assert target.read_bytes()


def test_retained_input_identity_detects_path_replacement_and_preserves_foreign_file(
    restore_modules,
    tmp_path: Path,
) -> None:
    _, restore = restore_modules
    path = tmp_path / "platform.dump"
    path.write_bytes(DUMP_BYTES)

    with restore._open_verified_file(path) as verified:
        try:
            path.unlink()
        except PermissionError:
            pytest.skip("the platform prevents replacing a retained open input file")
        path.write_bytes(b"foreign-replacement")
        with pytest.raises(restore.RestoreError):
            restore._read_verified_bytes(verified, require_non_empty=True)

    assert path.read_bytes() == b"foreign-replacement"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(extra="not-allowed"),
        lambda value: value.pop("createdAt"),
        lambda value: value.update(formatVersion=True),
        lambda value: value.update(formatVersion=1.0),
        lambda value: value.update(createdAt="2026-08-21T10:00:00+08:00"),
        lambda value: value.update(createdAt="2026-08-21T02:00:00.000000Z"),
        lambda value: value.update(databaseName=""),
        lambda value: value.update(alembicRevision=" "),
        lambda value: value.update(rowCounts={"users": 3}),
        lambda value: value["rowCounts"].update(extra=0),
        lambda value: value["rowCounts"].update(users=True),
        lambda value: value["rowCounts"].update(users=-1),
        lambda value: value.update(dumpSha256="A" * 64),
        lambda value: value.update(dumpSha256="not-a-sha"),
        lambda value: value.update(pgDumpVersion=""),
    ],
)
def test_restore_manifest_validation_is_exact_and_canonical(
    restore_modules,
    mutation,
) -> None:
    _, restore = restore_modules
    manifest = _restore_manifest()
    mutation(manifest)

    with pytest.raises(restore.RestoreError):
        restore._validate_manifest(manifest)


@pytest.mark.parametrize("dump_bytes", [b"", b"different-dump"])
def test_restore_rejects_empty_or_checksum_mismatched_dump_before_head_tool_or_database(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    dump_bytes: bytes,
) -> None:
    _, restore = restore_modules
    dump, manifest = _write_restore_inputs(tmp_path)
    dump.write_bytes(dump_bytes)
    monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", "1")
    monkeypatch.setenv("RESTORE_DATABASE_URL", RESTORE_DATABASE_URL)
    monkeypatch.setattr(
        restore,
        "_repository_heads",
        lambda: pytest.fail("repository head lookup must follow input verification"),
    )
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not run for an invalid dump"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(dump, manifest)


def test_restore_rejects_malformed_manifest_before_head_tool_or_database(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, restore = restore_modules
    dump, manifest = _write_restore_inputs(tmp_path)
    manifest.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("SUPERSONIC_ALLOW_DB_RESTORE", "1")
    monkeypatch.setenv("RESTORE_DATABASE_URL", RESTORE_DATABASE_URL)
    monkeypatch.setattr(
        restore,
        "_repository_heads",
        lambda: pytest.fail("repository head lookup must follow manifest verification"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(dump, manifest)


def test_repository_heads_use_configured_alembic_script_directory(
    restore_modules,
    monkeypatch,
) -> None:
    _, restore = restore_modules
    observed: dict[str, object] = {}

    class Config:
        def __init__(self, path: str) -> None:
            observed["config_path"] = Path(path)

    class Scripts:
        @classmethod
        def from_config(cls, config):
            observed["config"] = config
            return cls()

        def get_heads(self):
            return [REPOSITORY_HEAD]

    monkeypatch.setattr(restore, "Config", Config)
    monkeypatch.setattr(restore, "ScriptDirectory", Scripts)

    assert restore._repository_heads() == [REPOSITORY_HEAD]
    assert observed["config_path"] == REPOSITORY_ROOT / "apps" / "backend" / "alembic.ini"
    assert isinstance(observed["config"], Config)


@pytest.mark.parametrize("heads", [[], ["head-a", "head-b"]])
def test_restore_requires_exactly_one_repository_head_before_tool_or_database(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    heads: list[str],
) -> None:
    _, restore = restore_modules
    dump, manifest, _ = _install_restore_success(monkeypatch, restore, tmp_path)
    monkeypatch.setattr(restore, "_repository_heads", lambda: heads)
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not run without one repo head"),
    )
    monkeypatch.setattr(
        restore,
        "database_recovery_state",
        lambda connection: pytest.fail("the database must not be accessed without one repo head"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(dump, manifest)


def test_restore_rejects_manifest_revision_not_at_repository_head_before_tool_or_database(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, restore = restore_modules
    dump, manifest, _ = _install_restore_success(monkeypatch, restore, tmp_path)
    monkeypatch.setattr(restore, "_repository_heads", lambda: ["newer-head"])
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda *args, **kwargs: pytest.fail("pg_restore must not run for a stale manifest"),
    )
    monkeypatch.setattr(
        restore,
        "database_recovery_state",
        lambda connection: pytest.fail("the database must not be accessed for a stale manifest"),
    )

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(dump, manifest)


def test_database_recovery_state_uses_fixed_read_only_queries_and_sanitized_connection(
    restore_modules,
    monkeypatch,
) -> None:
    tools, _ = restore_modules
    executed: list[str] = []
    connect_kwargs: dict[str, object] = {}
    rows = iter([(REPOSITORY_HEAD,), (3,), (5,), (42,), (1,), (0,), (0,)])

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def execute(self, statement: str) -> None:
            executed.append(" ".join(statement.split()))

        def fetchone(self):
            return next(rows)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            executed.append("CONNECTION_EXIT")
            return None

        def cursor(self):
            return Cursor()

    def connect(**kwargs):
        connect_kwargs.update(kwargs)
        return Connection()

    monkeypatch.setenv("PGSERVICE", "redirect-service")
    monkeypatch.setenv("PGPASSWORD", "redirect-password")
    monkeypatch.setattr(tools.psycopg, "connect", connect)

    state = tools.database_recovery_state(tools.parse_database_url(RESTORE_DATABASE_URL))

    assert state == {
        "alembicRevision": REPOSITORY_HEAD,
        "rowCounts": {"users": 3, "platform_sessions": 5, "audit_events": 42},
        "invariants": {
            "enabledAdminCount": 1,
            "disabledUserActiveSessionCount": 0,
            "orphanRevokeReasonCount": 0,
        },
    }
    assert connect_kwargs["dbname"] == "supersonic_restore_test"
    assert connect_kwargs["password"] == RESTORE_PASSWORD
    assert executed == [
        "SET TRANSACTION READ ONLY",
        "SELECT version_num FROM alembic_version",
        "SELECT count(*) FROM users",
        "SELECT count(*) FROM platform_sessions",
        "SELECT count(*) FROM audit_events",
        "SELECT count(*) FROM users WHERE role = 'admin' AND disabled_at IS NULL",
        "SELECT count(*) FROM users AS u JOIN platform_sessions AS s ON s.user_id = u.id "
        "WHERE u.disabled_at IS NOT NULL AND s.revoked_at IS NULL "
        "AND s.expires_at > CURRENT_TIMESTAMP",
        "SELECT count(*) FROM platform_sessions WHERE revoke_reason IS NOT NULL "
        "AND revoked_at IS NULL",
        "CONNECTION_EXIT",
    ]


def test_restore_success_uses_exact_flags_and_minimal_safe_report(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, restore = restore_modules
    dump, manifest, calls = _install_restore_success(monkeypatch, restore, tmp_path)

    report = restore.restore_backup(dump, manifest)

    executable, arguments, connection = calls["tool"]
    assert executable == "pg_restore"
    assert arguments == [
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--single-transaction",
        "--dbname",
        "supersonic_restore_test",
        str(dump),
    ]
    assert connection.database == "supersonic_restore_test"
    assert calls["verification_connection"] is connection
    assert report == {
        "result": "ok",
        "databaseName": "supersonic_restore_test",
        "alembicRevision": REPOSITORY_HEAD,
        "rowCounts": {"users": 3, "platform_sessions": 5, "audit_events": 42},
        "dumpSha256": hashlib.sha256(DUMP_BYTES).hexdigest(),
        "appAcceptanceRequired": True,
    }
    serialized = json.dumps(report)
    argv_text = " ".join(arguments)
    for secret in (
        RESTORE_DATABASE_URL,
        RESTORE_PASSWORD,
        "restore-user",
        "127.0.0.1",
        "source-secret",
        "source-user",
    ):
        assert secret not in serialized
        assert secret not in argv_text


def test_pg_restore_helper_disables_shell_and_uses_only_sanitized_target_environment(
    restore_modules,
    monkeypatch,
) -> None:
    tools, _ = restore_modules
    observed: dict[str, object] = {}
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("PGSERVICE", "redirect-service")

    def run(argv, **kwargs):
        observed["argv"] = argv
        observed.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(tools.subprocess, "run", run)
    connection = tools.parse_database_url(RESTORE_DATABASE_URL)
    result = tools.run_postgres_tool("pg_restore", ["--clean", "safe.dump"], connection)

    assert result.returncode == 0
    assert observed["argv"] == ["pg_restore", "--clean", "safe.dump"]
    assert "shell" not in observed
    environment = observed["env"]
    assert environment["PGDATABASE"] == "supersonic_restore_test"
    assert environment["PGPASSWORD"] == RESTORE_PASSWORD
    assert environment["PGHOST"] == "127.0.0.1"
    assert environment["PGUSER"] == "restore-user"
    assert "DATABASE_URL" not in environment
    assert "PGSERVICE" not in environment
    assert DATABASE_URL not in " ".join(observed["argv"])
    assert RESTORE_DATABASE_URL not in " ".join(observed["argv"])


def test_pg_restore_failure_never_verifies_database_or_returns_success(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, restore = restore_modules
    dump, manifest, _ = _install_restore_success(monkeypatch, restore, tmp_path)
    monkeypatch.setattr(
        restore,
        "run_postgres_tool",
        lambda executable, arguments, connection: subprocess.CompletedProcess(
            [executable, *arguments],
            1,
            stdout="",
            stderr=RESTORE_DATABASE_URL,
        ),
    )
    monkeypatch.setattr(
        restore,
        "database_recovery_state",
        lambda connection: pytest.fail("failed pg_restore must not access the database"),
    )

    with pytest.raises(restore.RestoreError) as raised:
        restore.restore_backup(dump, manifest)

    assert RESTORE_DATABASE_URL not in str(raised.value)
    assert RESTORE_PASSWORD not in str(raised.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("alembicRevision", "wrong-revision"),
        ("users", 4),
        ("enabledAdminCount", 0),
        ("disabledUserActiveSessionCount", 1),
        ("orphanRevokeReasonCount", 1),
    ],
)
def test_restore_postverification_mismatch_never_returns_success(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    _, restore = restore_modules
    dump, manifest, _ = _install_restore_success(monkeypatch, restore, tmp_path)
    state = {
        "alembicRevision": REPOSITORY_HEAD,
        "rowCounts": {"users": 3, "platform_sessions": 5, "audit_events": 42},
        "invariants": {
            "enabledAdminCount": 1,
            "disabledUserActiveSessionCount": 0,
            "orphanRevokeReasonCount": 0,
        },
    }
    if field == "alembicRevision":
        state[field] = value
    elif field in state["rowCounts"]:
        state["rowCounts"][field] = value
    else:
        state["invariants"][field] = value
    monkeypatch.setattr(restore, "database_recovery_state", lambda connection: state)

    with pytest.raises(restore.RestoreError):
        restore.restore_backup(dump, manifest)


def test_restore_cli_help_scopes_success_and_live_acceptance_boundary(
    restore_modules,
    capsys,
) -> None:
    _, restore = restore_modules

    with pytest.raises(SystemExit) as raised:
        restore.main(["--help"])

    captured = capsys.readouterr()
    assert raised.value.code == 0
    help_text = " ".join(captured.out.casefold().split())
    assert "destructive" in help_text
    assert "isolated" in help_text
    assert "database restore verification" in help_text
    assert "application acceptance" in help_text
    assert "separate" in help_text
    assert "trusted operator-controlled input directory" in help_text
    assert "does not protect against malicious same-user mutation" in help_text


@pytest.mark.parametrize(
    "raised",
    [
        RuntimeError(RESTORE_DATABASE_URL),
        OSError(f"host=127.0.0.1 user=restore-user password={RESTORE_PASSWORD}"),
        ValueError(RESTORE_PASSWORD),
    ],
)
def test_restore_cli_failure_is_stable_safe_json_without_traceback_or_success(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    capsys,
    raised: Exception,
) -> None:
    _, restore = restore_modules
    monkeypatch.setattr(
        restore,
        "restore_backup",
        lambda dump, manifest: (_ for _ in ()).throw(raised),
    )

    exit_code = restore.main(
        [
            "--input",
            str(tmp_path / "platform.dump"),
            "--manifest",
            str(tmp_path / "platform.dump.manifest.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {"code": "restore_failed", "message": "Platform restore failed."}
    }
    for secret in (
        RESTORE_DATABASE_URL,
        RESTORE_PASSWORD,
        "127.0.0.1",
        "restore-user",
        "Traceback",
        "result",
    ):
        assert secret not in captured.err


def test_restore_cli_success_emits_one_exact_safe_json_object(
    restore_modules,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _, restore = restore_modules
    expected = {
        "result": "ok",
        "databaseName": "supersonic_restore_test",
        "alembicRevision": REPOSITORY_HEAD,
        "rowCounts": {"users": 3, "platform_sessions": 5, "audit_events": 42},
        "dumpSha256": hashlib.sha256(DUMP_BYTES).hexdigest(),
        "appAcceptanceRequired": True,
    }
    monkeypatch.setattr(restore, "restore_backup", lambda dump, manifest: expected)

    exit_code = restore.main(
        [
            "--input",
            str(tmp_path / "platform.dump"),
            "--manifest",
            str(tmp_path / "platform.dump.manifest.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == expected


def test_restore_source_contains_no_database_lifecycle_or_migration_commands() -> None:
    source = RESTORE_PATH.read_text(encoding="utf-8").casefold()

    assert "create database" not in source
    assert "drop database" not in source
    assert "alembic upgrade" not in source


def test_restore_env_example_is_commented_isolated_and_explicitly_destructive() -> None:
    lines = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    restore_url_lines = [line for line in lines if "RESTORE_DATABASE_URL=" in line]
    opt_in_lines = [line for line in lines if "SUPERSONIC_ALLOW_DB_RESTORE=" in line]

    assert len(restore_url_lines) == 1
    assert len(opt_in_lines) == 1
    assert restore_url_lines[0].lstrip().startswith("#")
    assert opt_in_lines[0].lstrip().startswith("#")
    assert "_restore_test" in restore_url_lines[0]
    nearby = " ".join(lines).casefold()
    assert "destructive" in nearby
    assert "isolated" in nearby
