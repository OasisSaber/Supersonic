from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.platform.audit_fallback import JsonlAuditFallback
from app.platform.audit_identity import AuditEventConflict
from app.platform.models import AuditDelivery, AuditEvent, AuditResult

SCRIPT_PATH = Path(__file__).parents[3] / "scripts" / "reconcile_audit_fallback.py"
REPOSITORY_ROOT = SCRIPT_PATH.parents[1]


def _load_cli_module():
    specification = importlib.util.spec_from_file_location("audit_reconcile_cli", SCRIPT_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _fallback_event() -> AuditEvent:
    return AuditEvent(
        id="11111111-1111-4111-8111-111111111111",
        occurred_at=datetime(2026, 8, 13, 12, tzinfo=UTC),
        action="cockpit.command",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
        parameters={"api_key": "must-not-write"},
    )


def test_cli_dry_run_prints_report_without_input_path(tmp_path, capsys) -> None:
    source = tmp_path / "audit-fallback.jsonl"
    JsonlAuditFallback(source).append(_fallback_event())
    module = _load_cli_module()

    exit_code = module.main(["--input", str(source), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "validated": 1,
        "imported": 0,
        "duplicates": 0,
        "dryRun": True,
    }
    assert str(source) not in captured.out
    assert str(source) not in captured.err
    assert source.is_file()


def test_cli_rejects_missing_database_configuration_without_revealing_input_path(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    source = tmp_path / "audit-fallback.jsonl"
    JsonlAuditFallback(source).append(_fallback_event())
    module = _load_cli_module()
    settings = type("Settings", (), {"database_url": None})()
    monkeypatch.setattr(module, "load_settings", lambda: settings)

    exit_code = module.main(["--input", str(source)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"]["code"] == "database_unconfigured"
    assert str(source) not in captured.err
    assert source.is_file()


def test_cli_does_not_disclose_raw_configuration_errors(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    source = tmp_path / "audit-fallback.jsonl"
    JsonlAuditFallback(source).append(_fallback_event())
    module = _load_cli_module()
    monkeypatch.setattr(
        module,
        "load_settings",
        lambda: (_ for _ in ()).throw(ValueError("postgresql://secret@example.test")),
    )

    exit_code = module.main(["--input", str(source)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"]["code"] == "reconciliation_invalid"
    assert "postgresql://secret@example.test" not in captured.err
    assert str(source) not in captured.err


def test_cli_reports_malformed_fallback_without_archiving_source(tmp_path, capsys) -> None:
    source = tmp_path / "audit-fallback.jsonl"
    source.write_text("not-json\n", encoding="utf-8")
    module = _load_cli_module()

    exit_code = module.main(["--input", str(source), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"]["code"] == "fallback_invalid"
    assert source.is_file()
    assert not (tmp_path / "audit-fallback.jsonl.reconciled").exists()


def test_cli_runs_from_repository_root_without_pythonpath(tmp_path) -> None:
    source = tmp_path / "audit-fallback.jsonl"
    JsonlAuditFallback(source).append(_fallback_event())
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input", str(source), "--dry-run"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {
        "validated": 1,
        "imported": 0,
        "duplicates": 0,
        "dryRun": True,
    }
    assert str(source) not in completed.stdout
    assert str(source) not in completed.stderr


def test_cli_rejects_missing_fallback_source(tmp_path, capsys) -> None:
    source = tmp_path / "does-not-exist.jsonl"
    module = _load_cli_module()

    exit_code = module.main(["--input", str(source), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"]["code"] == "fallback_missing"
    assert str(source) not in captured.err


def test_cli_rejects_invalid_arguments_without_disclosing_their_values(tmp_path, capsys) -> None:
    source = tmp_path / "audit-fallback.jsonl"
    secret_path = tmp_path / "private" / "secret-audit.jsonl"
    module = _load_cli_module()

    exit_code = module.main(["--input", str(source), f"--bogus={secret_path}"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"]["code"] == "arguments_invalid"
    assert str(source) not in captured.err
    assert str(secret_path) not in captured.err


def test_cli_reports_conflict_distinctly_and_leaves_source_unarchived(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    source = tmp_path / "audit-fallback.jsonl"
    JsonlAuditFallback(source).append(_fallback_event())
    module = _load_cli_module()
    monkeypatch.setattr(
        module,
        "reconcile_input",
        lambda path, dry_run: (_ for _ in ()).throw(
            AuditEventConflict(_fallback_event().id)
        ),
    )

    exit_code = module.main(["--input", str(source)])

    captured = capsys.readouterr()
    assert exit_code == 2
    error = json.loads(captured.err)["error"]
    assert error["code"] == "reconciliation_conflict"
    assert error["message"] == (
        f"Audit event {_fallback_event().id} conflicts with an existing audit fact."
    )
    assert str(source) not in captured.err
    assert source.is_file()
    assert not list(tmp_path.glob("audit-fallback.jsonl.reconciled-*"))


def test_cli_does_not_disclose_sqlalchemy_errors(tmp_path, monkeypatch, capsys) -> None:
    source = tmp_path / "audit-fallback.jsonl"
    JsonlAuditFallback(source).append(_fallback_event())
    module = _load_cli_module()
    secret = "postgresql://audit:secret@db.example.test/audit"
    monkeypatch.setattr(
        module,
        "reconcile_input",
        lambda path, dry_run: (_ for _ in ()).throw(SQLAlchemyError(secret)),
    )

    exit_code = module.main(["--input", str(source)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.err)["error"]["code"] == "reconciliation_failed"
    assert secret not in captured.err
    assert str(source) not in captured.err
