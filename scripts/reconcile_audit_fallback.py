"""Explicit local reconciliation for sanitized audit fallback files."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "apps" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.postgres.database import (  # noqa: E402
    create_database_engine,
    create_session_factory,
)
from app.adapters.postgres.readiness import SqlAlchemyPlatformReadiness  # noqa: E402
from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.platform.audit_fallback import AuditFallbackError, JsonlAuditFallback  # noqa: E402
from app.platform.audit_identity import AuditEventConflict  # noqa: E402
from app.platform.audit_reconciliation import (  # noqa: E402
    AuditReconciler,
    AuditReconciliationReport,
)
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402


class ReconciliationCliError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ReconciliationCliError(
            "arguments_invalid",
            "The audit reconciliation arguments are invalid.",
        )


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = _SafeArgumentParser(
        description="Reconcile one local Supersonic audit fallback file."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(arguments)


async def reconcile_input(path: Path, *, dry_run: bool) -> AuditReconciliationReport:
    if not path.is_file():
        raise ReconciliationCliError(
            "fallback_missing",
            "The requested audit fallback file does not exist.",
        )
    fallback = JsonlAuditFallback(path)
    if dry_run:
        return await AuditReconciler(uow_factory=_unused_uow_factory).reconcile_file(
            fallback,
            dry_run=True,
        )

    settings = load_settings()
    if settings.database_url is None:
        raise ReconciliationCliError(
            "database_unconfigured",
            "A configured platform database is required for reconciliation.",
        )
    engine = create_database_engine(settings.database_url)
    try:
        session_factory = create_session_factory(engine)
        readiness = SqlAlchemyPlatformReadiness(settings.database_url, engine=engine)
        await readiness.check()
        reconciler = AuditReconciler(
            uow_factory=lambda: SqlAlchemyPlatformUnitOfWork(session_factory)
        )
        return await reconciler.reconcile_file(fallback, dry_run=False)
    finally:
        await engine.dispose()


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        parsed = parse_args(arguments)
        report = asyncio.run(reconcile_input(parsed.input, dry_run=parsed.dry_run))
    except AuditFallbackError as error:
        return _write_error("fallback_invalid", str(error))
    except ReconciliationCliError as error:
        return _write_error(error.code, error.message)
    except AuditEventConflict as error:
        return _write_error(
            "reconciliation_conflict",
            f"Audit event {error.event_id} conflicts with an existing audit fact.",
        )
    except ValueError:
        return _write_error(
            "reconciliation_invalid",
            "The audit reconciliation configuration is invalid.",
        )
    except SQLAlchemyError:
        return _write_error(
            "reconciliation_failed",
            "The audit fallback could not be reconciled safely.",
        )
    except (OSError, RuntimeError):
        return _write_error(
            "reconciliation_failed",
            "The audit fallback could not be reconciled safely.",
        )
    print(
        json.dumps(
            {
                "validated": report.validated,
                "imported": report.imported,
                "duplicates": report.duplicates,
                "dryRun": report.dry_run,
            },
            separators=(",", ":"),
        )
    )
    return 0


def _unused_uow_factory() -> NoReturn:
    raise AssertionError("Dry-run reconciliation must not construct a Unit of Work.")


def _write_error(code: str, message: str) -> int:
    print(
        json.dumps({"error": {"code": code, "message": message}}),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
