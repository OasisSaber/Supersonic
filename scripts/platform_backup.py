"""Create a guarded atomic PostgreSQL backup for a trusted local operator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

from platform_db_tools import (
    database_metadata,
    parse_database_url,
    run_postgres_tool,
    tool_version,
)

_REQUIRED_TABLES = ("users", "platform_sessions", "audit_events")
_READ_BLOCK_SIZE = 1024 * 1024


class BackupError(RuntimeError):
    """A backup contract failure whose details must not be exposed by the CLI."""


@dataclass(slots=True)
class _FileAnchor:
    descriptor: int | None


@dataclass(frozen=True, slots=True)
class _OwnedFile:
    path: Path
    identity: tuple[int, int]
    anchor: _FileAnchor | None = None


@dataclass(frozen=True, slots=True)
class _OperationLock:
    owned: _OwnedFile
    descriptor: int


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise BackupError("The platform backup arguments are invalid.")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _canonical_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BackupError("The backup timestamp is invalid.")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _identity_from_status(status: os.stat_result) -> tuple[int, int]:
    return status.st_dev, status.st_ino


def _file_identity(path: Path) -> tuple[int, int]:
    return _identity_from_status(path.lstat())


def _require_regular_identity(
    status: os.stat_result, identity: tuple[int, int]
) -> None:
    if not stat.S_ISREG(status.st_mode) or _identity_from_status(status) != identity:
        raise BackupError("An owned backup file changed unexpectedly.")


def _assert_owned_path(owned: _OwnedFile) -> os.stat_result:
    try:
        status = owned.path.lstat()
    except FileNotFoundError as error:
        raise BackupError("An owned backup file is unavailable.") from error
    _require_regular_identity(status, owned.identity)
    if owned.anchor is not None and owned.anchor.descriptor is not None:
        try:
            anchor_status = os.fstat(owned.anchor.descriptor)
        except OSError as error:
            raise BackupError("An owned backup file anchor is unavailable.") from error
        _require_regular_identity(anchor_status, owned.identity)
    return status


def _close_quietly(descriptor: int) -> None:
    try:
        os.close(descriptor)
    except OSError:
        pass


def _create_owned_temp(destination: Path) -> _OwnedFile:
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    path = Path(raw_path)
    identity: tuple[int, int] | None = None
    try:
        status = os.fstat(descriptor)
        identity = _identity_from_status(status)
        _require_regular_identity(status, identity)
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        _require_regular_identity(path.lstat(), identity)
        anchor = _FileAnchor(descriptor) if os.name == "posix" else None
        if anchor is None:
            os.close(descriptor)
    except BaseException:
        if identity is None and os.stat in os.supports_fd:
            try:
                fallback_status = os.stat(descriptor)
                fallback_identity = _identity_from_status(fallback_status)
                _require_regular_identity(fallback_status, fallback_identity)
                identity = fallback_identity
            except (OSError, BackupError):
                pass
        _close_quietly(descriptor)
        if identity is not None:
            try:
                _require_regular_identity(path.lstat(), identity)
                path.unlink()
            except (FileNotFoundError, OSError, BackupError):
                pass
        raise
    assert identity is not None
    return _OwnedFile(path=path, identity=identity, anchor=anchor)


def _open_owned_descriptor(owned: _OwnedFile, flags: int) -> int:
    _assert_owned_path(owned)
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    binary = getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(owned.path, flags | no_follow | binary)
    except OSError as error:
        raise BackupError("An owned backup file cannot be opened safely.") from error
    try:
        _require_regular_identity(os.fstat(descriptor), owned.identity)
        _assert_owned_path(owned)
    except Exception:
        _close_quietly(descriptor)
        raise
    return descriptor


def _read_owned_bytes(owned: _OwnedFile, *, require_non_empty: bool) -> bytes:
    descriptor = _open_owned_descriptor(owned, os.O_RDONLY)
    try:
        initial_status = os.fstat(descriptor)
        if require_non_empty and initial_status.st_size <= 0:
            raise BackupError("The PostgreSQL backup tool produced no dump.")
        chunks: list[bytes] = []
        while block := os.read(descriptor, _READ_BLOCK_SIZE):
            chunks.append(block)
        final_status = os.fstat(descriptor)
        _require_regular_identity(final_status, owned.identity)
        if (
            final_status.st_size != initial_status.st_size
            or final_status.st_mtime_ns != initial_status.st_mtime_ns
        ):
            raise BackupError("An owned backup file changed while it was read.")
        _assert_owned_path(owned)
        return b"".join(chunks)
    finally:
        _close_quietly(descriptor)


def sha256_file(owned: _OwnedFile) -> str:
    descriptor = _open_owned_descriptor(owned, os.O_RDONLY)
    try:
        initial_status = os.fstat(descriptor)
        if initial_status.st_size <= 0:
            raise BackupError("The PostgreSQL backup tool produced no dump.")
        digest = hashlib.sha256()
        while block := os.read(descriptor, _READ_BLOCK_SIZE):
            digest.update(block)
        final_status = os.fstat(descriptor)
        _require_regular_identity(final_status, owned.identity)
        if (
            final_status.st_size != initial_status.st_size
            or final_status.st_mtime_ns != initial_status.st_mtime_ns
        ):
            raise BackupError("An owned backup file changed while it was hashed.")
        _assert_owned_path(owned)
        return digest.hexdigest()
    finally:
        _close_quietly(descriptor)


def _write_manifest(owned: _OwnedFile, manifest: dict[str, object]) -> bytes:
    serialized = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    descriptor = _open_owned_descriptor(owned, os.O_WRONLY)
    try:
        os.ftruncate(descriptor, 0)
        offset = 0
        while offset < len(serialized):
            written = os.write(descriptor, serialized[offset:])
            if written <= 0:
                raise OSError("manifest write made no progress")
            offset += written
        os.fsync(descriptor)
        status = os.fstat(descriptor)
        _require_regular_identity(status, owned.identity)
        if status.st_size != len(serialized):
            raise BackupError("The backup manifest write is incomplete.")
        _assert_owned_path(owned)
    finally:
        _close_quietly(descriptor)
    return serialized


def _remove_published_if_owned(path: Path, identity: tuple[int, int]) -> bool:
    try:
        status = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(status.st_mode) or _identity_from_status(status) != identity:
        return False
    path.unlink()
    return True


def _remove_owned(owned: _OwnedFile | None) -> None:
    if owned is None:
        return
    try:
        _remove_published_if_owned(owned.path, owned.identity)
    finally:
        _close_owned_anchor(owned)


def _close_owned_anchor(owned: _OwnedFile | None) -> None:
    if owned is None or owned.anchor is None or owned.anchor.descriptor is None:
        return
    descriptor = owned.anchor.descriptor
    owned.anchor.descriptor = None
    _close_quietly(descriptor)


def _destination_occupied(path: Path) -> bool:
    return os.path.lexists(path)


def _publish_no_replace(source: _OwnedFile, destination: Path) -> _OwnedFile:
    _assert_owned_path(source)
    try:
        os.link(source.path, destination, follow_symlinks=False)
    except FileExistsError as error:
        raise BackupError("The backup output already exists.") from error
    except OSError as error:
        raise BackupError("The backup output cannot be published safely.") from error

    try:
        destination_status = destination.lstat()
    except FileNotFoundError as error:
        raise BackupError("The published backup file disappeared.") from error
    destination_identity = _identity_from_status(destination_status)
    if (
        not stat.S_ISREG(destination_status.st_mode)
        or destination_identity != source.identity
    ):
        raise BackupError("The published backup file changed during its claim.")

    try:
        _assert_owned_path(source)
        if not _remove_published_if_owned(source.path, source.identity):
            raise BackupError("The owned backup source changed during publication.")
        published = _OwnedFile(
            path=destination,
            identity=source.identity,
            anchor=source.anchor,
        )
        _assert_owned_path(published)
        return published
    except Exception:
        try:
            _remove_published_if_owned(destination, source.identity)
        except OSError:
            pass
        raise


def _validate_output_directory(directory: Path) -> None:
    status = directory.lstat()
    if not stat.S_ISDIR(status.st_mode):
        raise BackupError("The backup output directory is invalid.")
    if os.name == "posix":
        if status.st_uid != os.geteuid():
            raise BackupError(
                "The backup output directory must be owned by the operator."
            )
        if stat.S_IMODE(status.st_mode) & 0o022:
            raise BackupError("The backup output directory permissions are unsafe.")


def _acquire_operation_lock(output: Path) -> _OperationLock:
    lock_path = output.with_name(f".{output.name}.backup.lock")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except FileExistsError as error:
        raise BackupError("A backup operation is already using this output.") from error
    except OSError as error:
        raise BackupError(
            "The backup operation lock cannot be created safely."
        ) from error
    try:
        status = os.fstat(descriptor)
        identity = _identity_from_status(status)
        _require_regular_identity(status, identity)
        _require_regular_identity(lock_path.lstat(), identity)
        return _OperationLock(_OwnedFile(lock_path, identity), descriptor)
    except Exception:
        _close_quietly(descriptor)
        try:
            _remove_published_if_owned(lock_path, identity)
        except (OSError, UnboundLocalError):
            pass
        raise


def _release_operation_lock(operation_lock: _OperationLock | None) -> None:
    if operation_lock is None:
        return
    _close_quietly(operation_lock.descriptor)
    try:
        _remove_owned(operation_lock.owned)
    except OSError:
        pass


def _validated_manifest_metadata(
    metadata: dict[str, object],
) -> tuple[str, dict[str, int]]:
    revision = metadata.get("alembicRevision")
    if not isinstance(revision, str) or not revision.strip():
        raise BackupError("The backup metadata is invalid.")

    raw_counts = metadata.get("rowCounts")
    if not isinstance(raw_counts, dict):
        raise BackupError("The backup metadata is invalid.")
    row_counts: dict[str, int] = {}
    for table in _REQUIRED_TABLES:
        count = raw_counts.get(table)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise BackupError("The backup metadata is invalid.")
        row_counts[table] = count
    return revision, row_counts


def _verify_dump(published_dump: _OwnedFile, expected_sha256: str) -> None:
    if sha256_file(published_dump) != expected_sha256:
        raise BackupError("The published backup checksum changed.")


def _verify_manifest(published_manifest: _OwnedFile, expected_bytes: bytes) -> None:
    if _read_owned_bytes(published_manifest, require_non_empty=True) != expected_bytes:
        raise BackupError("The published backup manifest changed.")


def create_backup(output: Path) -> dict[str, object]:
    raw_url = os.environ.get("DATABASE_URL")
    if not raw_url:
        raise BackupError("A configured platform database is required.")
    connection = parse_database_url(raw_url)

    expanded_output = output.expanduser()
    if not expanded_output.is_absolute():
        expanded_output = Path.cwd() / expanded_output
    output = expanded_output.parent.resolve() / expanded_output.name
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    if _destination_occupied(output) or _destination_occupied(manifest_path):
        raise BackupError("The backup output already exists.")

    output.parent.mkdir(parents=True, exist_ok=True)
    _validate_output_directory(output.parent)
    operation_lock: _OperationLock | None = None
    dump_temp: _OwnedFile | None = None
    manifest_temp: _OwnedFile | None = None
    published_dump: _OwnedFile | None = None
    published_manifest: _OwnedFile | None = None
    try:
        operation_lock = _acquire_operation_lock(output)
        if _destination_occupied(output) or _destination_occupied(manifest_path):
            raise BackupError("The backup output already exists.")
        dump_temp = _create_owned_temp(output)
        manifest_temp = _create_owned_temp(manifest_path)

        version = tool_version("pg_dump")
        result = run_postgres_tool(
            "pg_dump",
            [
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(dump_temp.path),
            ],
            connection,
        )
        if result.returncode != 0:
            raise BackupError("The PostgreSQL backup tool failed.")

        dump_sha256 = sha256_file(dump_temp)
        metadata = database_metadata(connection)
        revision, row_counts = _validated_manifest_metadata(metadata)
        manifest: dict[str, object] = {
            "formatVersion": 1,
            "createdAt": _canonical_utc(_utc_now()),
            "databaseName": connection.database,
            "alembicRevision": revision,
            "rowCounts": row_counts,
            "dumpSha256": dump_sha256,
            "pgDumpVersion": version,
        }
        manifest_bytes = _write_manifest(manifest_temp, manifest)

        if _destination_occupied(output) or _destination_occupied(manifest_path):
            raise BackupError("The backup output already exists.")
        published_dump = _publish_no_replace(dump_temp, output)
        dump_temp = None
        _verify_dump(published_dump, dump_sha256)
        published_manifest = _publish_no_replace(manifest_temp, manifest_path)
        manifest_temp = None
        _verify_manifest(published_manifest, manifest_bytes)
        _verify_dump(published_dump, dump_sha256)
        _close_owned_anchor(published_manifest)
        _close_owned_anchor(published_dump)
        return manifest
    except Exception:
        for published in (published_manifest, published_dump):
            try:
                _remove_owned(published)
            except OSError:
                pass
        for temporary in (dump_temp, manifest_temp):
            try:
                _remove_owned(temporary)
            except OSError:
                pass
        raise
    finally:
        _release_operation_lock(operation_lock)


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = _SafeArgumentParser(
        description=(
            "Create a Supersonic PostgreSQL platform backup during a maintenance window.\n"
            "Stop platform writers before running this command.\n"
            "Use a trusted operator-owned output directory with exclusive cooperative access.\n"
            "The operation lock prevents cooperating backup commands from colliding; it does "
            "not protect against malicious same-user mutation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(arguments)


def _write_error() -> int:
    print(
        json.dumps(
            {
                "error": {
                    "code": "backup_failed",
                    "message": "Platform backup failed.",
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
        manifest = create_backup(parsed.output)
    except Exception:
        return _write_error()

    print(
        json.dumps(
            {
                "result": "ok",
                "databaseName": manifest["databaseName"],
                "alembicRevision": manifest["alembicRevision"],
                "dumpSha256": manifest["dumpSha256"],
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
