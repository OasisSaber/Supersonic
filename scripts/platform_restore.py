"""Verify and restore a platform backup into an isolated PostgreSQL test target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from alembic.config import Config
from alembic.script import ScriptDirectory

from platform_db_tools import (
    PostgresConnection,
    database_recovery_state,
    database_target_key,
    parse_database_url,
    run_postgres_tool,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_ALEMBIC_CONFIG = _REPOSITORY_ROOT / "apps" / "backend" / "alembic.ini"
_MANIFEST_KEYS = frozenset(
    {
        "formatVersion",
        "createdAt",
        "databaseName",
        "alembicRevision",
        "rowCounts",
        "dumpSha256",
        "pgDumpVersion",
    }
)
_REQUIRED_TABLES = ("users", "platform_sessions", "audit_events")
_INVARIANT_KEYS = frozenset(
    {
        "enabledAdminCount",
        "disabledUserActiveSessionCount",
        "orphanRevokeReasonCount",
    }
)
_READ_BLOCK_SIZE = 1024 * 1024
_MAX_MANIFEST_BYTES = 1024 * 1024
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SAFE_RESTORE_DATABASE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*_restore_test$")
_UTC_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?Z$"
)


class RestoreError(RuntimeError):
    """A restore contract failure whose details must not reach CLI output."""


@dataclass(frozen=True, slots=True)
class _VerifiedFile:
    path: Path
    descriptor: int
    identity: tuple[int, int]


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise RestoreError("The platform restore arguments are invalid.")


def _identity(status: os.stat_result) -> tuple[int, int]:
    return status.st_dev, status.st_ino


def _absolute_input_path(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    try:
        parent = expanded.parent.resolve(strict=True)
    except OSError as error:
        raise RestoreError("A restore input directory is unavailable.") from error
    return parent / expanded.name


def _require_regular_status(
    status: os.stat_result,
    expected_identity: tuple[int, int] | None = None,
) -> tuple[int, int]:
    observed_identity = _identity(status)
    if not stat.S_ISREG(status.st_mode):
        raise RestoreError("A restore input is not a regular file.")
    if expected_identity is not None and observed_identity != expected_identity:
        raise RestoreError("A restore input changed unexpectedly.")
    return observed_identity


def _assert_verified_path(verified: _VerifiedFile) -> os.stat_result:
    try:
        status = verified.path.lstat()
    except OSError as error:
        raise RestoreError("A restore input became unavailable.") from error
    _require_regular_status(status, verified.identity)
    return status


@contextmanager
def _open_verified_file(path: Path) -> Iterator[_VerifiedFile]:
    path = _absolute_input_path(path)
    try:
        initial_status = path.lstat()
    except OSError as error:
        raise RestoreError("A restore input is unavailable.") from error
    expected_identity = _require_regular_status(initial_status)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RestoreError("A restore input cannot be opened safely.") from error
    try:
        _require_regular_status(os.fstat(descriptor), expected_identity)
        verified = _VerifiedFile(path, descriptor, expected_identity)
        _assert_verified_path(verified)
        yield verified
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass


def _read_verified_bytes(
    verified: _VerifiedFile,
    *,
    require_non_empty: bool,
    maximum_bytes: int | None = None,
) -> bytes:
    _assert_verified_path(verified)
    initial_status = os.fstat(verified.descriptor)
    _require_regular_status(initial_status, verified.identity)
    if require_non_empty and initial_status.st_size <= 0:
        raise RestoreError("A restore input is empty.")
    if maximum_bytes is not None and initial_status.st_size > maximum_bytes:
        raise RestoreError("A restore input exceeds its safe size limit.")
    os.lseek(verified.descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while block := os.read(verified.descriptor, _READ_BLOCK_SIZE):
        total += len(block)
        if maximum_bytes is not None and total > maximum_bytes:
            raise RestoreError("A restore input exceeds its safe size limit.")
        chunks.append(block)
    _assert_stable_read(verified, initial_status)
    return b"".join(chunks)


def _sha256_verified_file(verified: _VerifiedFile) -> str:
    _assert_verified_path(verified)
    initial_status = os.fstat(verified.descriptor)
    _require_regular_status(initial_status, verified.identity)
    if initial_status.st_size <= 0:
        raise RestoreError("The restore dump is empty.")
    os.lseek(verified.descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while block := os.read(verified.descriptor, _READ_BLOCK_SIZE):
        digest.update(block)
    _assert_stable_read(verified, initial_status)
    return digest.hexdigest()


def _assert_stable_read(
    verified: _VerifiedFile, initial_status: os.stat_result
) -> None:
    final_status = os.fstat(verified.descriptor)
    _require_regular_status(final_status, verified.identity)
    if (
        final_status.st_size != initial_status.st_size
        or final_status.st_mtime_ns != initial_status.st_mtime_ns
    ):
        raise RestoreError("A restore input changed while it was read.")
    _assert_verified_path(verified)


def _canonical_utc_timestamp(value: object) -> str:
    if not isinstance(value, str) or not _UTC_TIMESTAMP_PATTERN.fullmatch(value):
        raise RestoreError("The restore manifest timestamp is invalid.")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as error:
        raise RestoreError("The restore manifest timestamp is invalid.") from error
    canonical = parsed.isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise RestoreError("The restore manifest timestamp is not canonical.")
    return value


def _nonempty_string(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise RestoreError("The restore manifest contains an invalid string.")
    return value


def _nonnegative_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RestoreError("The restore manifest contains an invalid count.")
    return value


def _validate_manifest(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != _MANIFEST_KEYS:
        raise RestoreError("The restore manifest shape is invalid.")
    format_version = value["formatVersion"]
    if (
        not isinstance(format_version, int)
        or isinstance(format_version, bool)
        or format_version != 1
    ):
        raise RestoreError("The restore manifest version is unsupported.")
    created_at = _canonical_utc_timestamp(value["createdAt"])
    database_name = _nonempty_string(value["databaseName"])
    alembic_revision = _nonempty_string(value["alembicRevision"])
    pg_dump_version = _nonempty_string(value["pgDumpVersion"])
    dump_sha256 = value["dumpSha256"]
    if not isinstance(dump_sha256, str) or not _SHA256_PATTERN.fullmatch(dump_sha256):
        raise RestoreError("The restore manifest checksum is invalid.")
    raw_counts = value["rowCounts"]
    if not isinstance(raw_counts, dict) or set(raw_counts) != set(_REQUIRED_TABLES):
        raise RestoreError("The restore manifest row counts are invalid.")
    row_counts = {
        table: _nonnegative_integer(raw_counts[table]) for table in _REQUIRED_TABLES
    }
    return {
        "formatVersion": 1,
        "createdAt": created_at,
        "databaseName": database_name,
        "alembicRevision": alembic_revision,
        "rowCounts": row_counts,
        "dumpSha256": dump_sha256,
        "pgDumpVersion": pg_dump_version,
    }


def _read_manifest(verified: _VerifiedFile) -> dict[str, object]:
    raw = _read_verified_bytes(
        verified,
        require_non_empty=True,
        maximum_bytes=_MAX_MANIFEST_BYTES,
    )
    try:
        decoded = raw.decode("utf-8")
        parsed = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RestoreError("The restore manifest cannot be decoded safely.") from error
    return _validate_manifest(parsed)


def _repository_heads() -> list[str]:
    configuration = Config(str(_ALEMBIC_CONFIG))
    scripts = ScriptDirectory.from_config(configuration)
    return [str(head) for head in scripts.get_heads()]


def _target_connection() -> PostgresConnection:
    if os.environ.get("SUPERSONIC_ALLOW_DB_RESTORE") != "1":
        raise RestoreError("Explicit restore opt-in is required.")
    raw_target = os.environ.get("RESTORE_DATABASE_URL")
    if not raw_target:
        raise RestoreError("An isolated restore target is required.")
    try:
        target = parse_database_url(raw_target)
    except ValueError as error:
        raise RestoreError("The isolated restore target is invalid.") from error
    if not _SAFE_RESTORE_DATABASE_PATTERN.fullmatch(target.database):
        raise RestoreError("The restore target is not an isolated test database.")

    raw_source = os.environ.get("DATABASE_URL")
    if raw_source:
        try:
            source = parse_database_url(raw_source)
        except ValueError as error:
            raise RestoreError("The configured source database is invalid.") from error
        if database_target_key(source) == database_target_key(target):
            raise RestoreError("The restore target matches the source database.")
    return target


def _adjacent_manifest(dump: Path, manifest: Path) -> bool:
    return manifest == dump.with_suffix(dump.suffix + ".manifest.json")


def _validated_recovery_state(
    state: object,
    *,
    expected_revision: str,
    expected_counts: Mapping[str, int],
) -> tuple[str, dict[str, int]]:
    if not isinstance(state, dict):
        raise RestoreError("The restored database verification is invalid.")
    revision = state.get("alembicRevision")
    if revision != expected_revision:
        raise RestoreError("The restored database revision does not match.")
    raw_counts = state.get("rowCounts")
    if not isinstance(raw_counts, dict) or set(raw_counts) != set(_REQUIRED_TABLES):
        raise RestoreError("The restored database row counts are invalid.")
    counts = {
        table: _nonnegative_integer(raw_counts[table]) for table in _REQUIRED_TABLES
    }
    if counts != dict(expected_counts):
        raise RestoreError("The restored database row counts do not match.")

    invariants = state.get("invariants")
    if not isinstance(invariants, dict) or set(invariants) != _INVARIANT_KEYS:
        raise RestoreError("The restored database invariants are invalid.")
    checked_invariants = {
        key: _nonnegative_integer(invariants[key]) for key in _INVARIANT_KEYS
    }
    if checked_invariants["enabledAdminCount"] < 1:
        raise RestoreError("The restored database has no enabled administrator.")
    if checked_invariants["disabledUserActiveSessionCount"] != 0:
        raise RestoreError("A disabled user has an active session after restore.")
    if checked_invariants["orphanRevokeReasonCount"] != 0:
        raise RestoreError("A restored session has an invalid revocation state.")
    return revision, counts


def restore_backup(dump: Path, manifest_path: Path) -> dict[str, object]:
    target = _target_connection()
    dump_path = _absolute_input_path(dump)
    manifest_file_path = _absolute_input_path(manifest_path)
    if not _adjacent_manifest(dump_path, manifest_file_path):
        raise RestoreError("The restore manifest must be adjacent to its dump.")

    with ExitStack() as stack:
        verified_dump = stack.enter_context(_open_verified_file(dump_path))
        verified_manifest = stack.enter_context(_open_verified_file(manifest_file_path))
        manifest = _read_manifest(verified_manifest)
        dump_sha256 = _sha256_verified_file(verified_dump)
        if dump_sha256 != manifest["dumpSha256"]:
            raise RestoreError("The restore dump checksum does not match its manifest.")

        try:
            heads = _repository_heads()
        except Exception as error:
            raise RestoreError(
                "The repository migration head is unavailable."
            ) from error
        if len(heads) != 1 or not heads[0]:
            raise RestoreError("The repository must have exactly one migration head.")
        repository_head = heads[0]
        if manifest["alembicRevision"] != repository_head:
            raise RestoreError(
                "The backup revision does not match the repository head."
            )

        _assert_verified_path(verified_dump)
        _assert_verified_path(verified_manifest)
        result = run_postgres_tool(
            "pg_restore",
            [
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-acl",
                "--single-transaction",
                "--dbname",
                target.database,
                str(verified_dump.path),
            ],
            target,
        )
        if result.returncode != 0:
            raise RestoreError("The PostgreSQL restore tool failed.")
        _assert_verified_path(verified_dump)
        _assert_verified_path(verified_manifest)

        try:
            recovery_state = database_recovery_state(target)
        except Exception as error:
            raise RestoreError(
                "The restored database could not be verified."
            ) from error
        revision, row_counts = _validated_recovery_state(
            recovery_state,
            expected_revision=repository_head,
            expected_counts=manifest["rowCounts"],
        )

    return {
        "result": "ok",
        "databaseName": target.database,
        "alembicRevision": revision,
        "rowCounts": row_counts,
        "dumpSha256": dump_sha256,
        "appAcceptanceRequired": True,
    }


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = _SafeArgumentParser(
        description=(
            "Perform destructive database restore verification against an explicitly isolated "
            "test target. This command only verifies the restored database; application "
            "acceptance is a separate Task 11 rehearsal. It does not manage database lifecycle "
            "or run migrations. Use a trusted operator-controlled input directory with "
            "exclusive cooperative access. This does not protect against malicious same-user "
            "mutation."
        )
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args(arguments)


def _write_error() -> int:
    print(
        json.dumps(
            {
                "error": {
                    "code": "restore_failed",
                    "message": "Platform restore failed.",
                }
            },
            separators=(",", ":"),
        ),
        file=sys.stderr,
    )
    return 1


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        parsed = parse_args(arguments)
        report = restore_backup(parsed.input, parsed.manifest)
    except Exception:
        return _write_error()
    print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
