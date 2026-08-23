"""Contract tests for repository-safe Slice E recovery evidence templates."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "deliverables" / "platform-recovery"
G4_MERGE_CHECKPOINT_SHA = "cb6ab6645313716e9ed54c8ecb49c27b3d918f37"
POST_MERGE_GATE_STATUS = "satisfied"
POST_MERGE_GATE_REQUIREMENT = "human_review_and_merge_completed"
JSON_EXAMPLES = {
    "backup-manifest.example.json",
    "restore-report.example.json",
    "acceptance.example.json",
}
JSON_EVIDENCE = {
    "backup-manifest.json",
    "restore-report.json",
    "acceptance.json",
}
JSON_FILES = JSON_EXAMPLES | JSON_EVIDENCE
SANITIZED_SCREENSHOTS = {
    "screenshots/platform-service-unavailable.png",
    "screenshots/restored-admin-audit.png",
    "screenshots/restored-admin-users.png",
    "screenshots/restored-revoked-sessions.png",
}
EXPECTED_FILES = (
    JSON_FILES
    | {
        "README.md",
        "RECOVERY_ACCEPTANCE_TEMPLATE.md",
        "screenshots/.gitkeep",
    }
    | SANITIZED_SCREENSHOTS
)
BACKUP_KEYS = {
    "formatVersion",
    "createdAt",
    "databaseName",
    "alembicRevision",
    "rowCounts",
    "dumpSha256",
    "pgDumpVersion",
}
ROW_COUNT_KEYS = {"users", "platform_sessions", "audit_events"}
FORBIDDEN_JSON_KEY_PARTS = {
    "password",
    "password_hash",
    "token",
    "cookie",
    "pgpassword",
    "private_key",
    "dsn",
    "url",
    "host",
    "username",
}
FORBIDDEN_SUCCESS_WORDS = re.compile(
    r"\b(?:passed|passing|success(?:ful(?:ly)?)?|complete(?:d|ion)?|ok|merged)\b",
    re.IGNORECASE,
)
SECRET_OR_PAYLOAD_PATTERN = re.compile(
    r"(?:postgres(?:ql)?(?:\+\w+)?://|PGPASSWORD\s*=|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\b(?:password|token|cookie|dsn)\s*[:=]\s*[^\s`]+)",
    re.IGNORECASE,
)


def load_json(name: str) -> dict[str, Any]:
    value = json.loads((EVIDENCE_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{name} must contain one JSON object")
    return value


def iter_items(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from iter_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_items(child)


def iter_values(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_values(child)
    else:
        yield value


def is_absolute_path(value: str) -> bool:
    windows_path = PureWindowsPath(value)
    return (
        PurePosixPath(value).is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or bool(windows_path.root)
    )


def iter_reference_fields(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = key.lower()
            if normalized_key in {
                "backupmanifest",
                "restorereport",
            } or normalized_key.endswith(("reference", "references", "directory")):
                yield key, child
            yield from iter_reference_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_reference_fields(child)


def is_safe_repository_reference(value: str) -> bool:
    if not value or "\\" in value or is_absolute_path(value):
        return False
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        return False
    path = PurePosixPath(value)
    if path.as_posix() != value:
        return False
    candidate = ROOT.joinpath(*path.parts).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return False
    return candidate.exists()


class RecoveryEvidenceTemplateTests(unittest.TestCase):
    def test_expected_repository_safe_template_files_exist(self):
        missing = sorted(
            path for path in EXPECTED_FILES if not (EVIDENCE_ROOT / path).is_file()
        )
        self.assertEqual([], missing)

    def test_every_json_example_parses_and_only_examples_are_present(self):
        names = {path.name for path in EVIDENCE_ROOT.glob("*.json") if path.is_file()}
        self.assertEqual(JSON_FILES, names)
        for name in sorted(JSON_FILES):
            self.assertIsInstance(load_json(name), dict)

    def test_backup_manifest_matches_the_strict_task_8_schema(self):
        for name in ("backup-manifest.example.json", "backup-manifest.json"):
            manifest = load_json(name)
            self.assertEqual(BACKUP_KEYS, set(manifest))
            self.assertEqual(1, manifest["formatVersion"])
            self.assertIs(type(manifest["formatVersion"]), int)
            self.assertEqual(ROW_COUNT_KEYS, set(manifest["rowCounts"]))
            for count in manifest["rowCounts"].values():
                self.assertIs(type(count), int)
                self.assertGreaterEqual(count, 0)
            self.assertRegex(
                manifest["createdAt"],
                r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$",
            )
            self.assertRegex(manifest["dumpSha256"], r"^[0-9a-f]{64}$")

    def test_examples_are_sanitized_and_use_only_pending_semantics(self):
        for name in sorted(JSON_EXAMPLES):
            path = EVIDENCE_ROOT / name
            text = path.read_text(encoding="utf-8")
            value = load_json(name)
            self.assertIsNone(SECRET_OR_PAYLOAD_PATTERN.search(text), name)
            self.assertIsNone(FORBIDDEN_SUCCESS_WORDS.search(text), name)
            self.assertFalse(any(child is True for _, child in iter_items(value)))
            for child in iter_values(value):
                if isinstance(child, str):
                    self.assertFalse(is_absolute_path(child), f"{name}: {child!r}")
            for key, child in iter_items(value):
                normalized_key = key.lower().replace("-", "_")
                self.assertFalse(
                    any(part in normalized_key for part in FORBIDDEN_JSON_KEY_PARTS),
                    f"sensitive key {key!r} in {name}",
                )
                if key.lower().endswith("status"):
                    self.assertIn(child, {"pending", "not_run"})

    def test_absolute_path_detector_covers_posix_windows_and_unc_forms(self):
        for value in (
            "/opt/recovery/report.json",
            "/mnt/evidence",
            "/workspace/output",
            "/etc/postgresql.conf",
            "C:\\recovery\\report.json",
            "D:/recovery/report.json",
            "\\\\server\\share\\report.json",
            "//server/share/report.json",
        ):
            self.assertTrue(is_absolute_path(value), value)
        for value in (
            "deliverables/platform-recovery/restore-report.example.json",
            "screenshots/example.png",
            "--clean",
        ):
            self.assertFalse(is_absolute_path(value), value)

    def test_json_reference_fields_are_normalized_existing_repository_paths(self):
        for name in sorted(JSON_FILES):
            for key, value in iter_reference_fields(load_json(name)):
                references = value if isinstance(value, list) else [value]
                for reference in references:
                    if reference is None:
                        continue
                    self.assertIsInstance(reference, str, f"{name}: {key}")
                    self.assertTrue(
                        is_safe_repository_reference(reference),
                        f"{name}: {key}={reference!r}",
                    )

    def test_restore_and_acceptance_cover_required_recovery_dimensions(self):
        restore = load_json("restore-report.example.json")
        acceptance = load_json("acceptance.example.json")

        self.assertIs(restore["dumpCommitted"], False)
        self.assertEqual("isolated_restore_test", restore["targetKind"])
        self.assertEqual(
            "deliverables/platform-recovery/backup-manifest.example.json",
            restore["backupManifest"],
        )
        self.assertEqual(
            {"checksum", "repositoryAlembicRevision"}, set(restore["preflight"])
        )
        self.assertEqual(
            {"restoredAlembicRevision", "rowCounts", "invariants"},
            set(restore["verification"]),
        )
        self.assertEqual(
            ROW_COUNT_KEYS, set(restore["verification"]["rowCounts"]["expected"])
        )
        self.assertEqual(
            ROW_COUNT_KEYS, set(restore["verification"]["rowCounts"]["observed"])
        )
        self.assertEqual(
            {
                "enabledAdminExists",
                "disabledUsersHaveNoActiveSessions",
                "revokeReasonRequiresRevokedAt",
            },
            set(restore["verification"]["invariants"]["checks"]),
        )

        self.assertIs(acceptance["dumpCommitted"], False)
        self.assertEqual("isolated_restore_test", acceptance["targetKind"])
        self.assertEqual(
            {"disabledAccountPersistence", "sessionRevocationPersistence"},
            set(acceptance["persistence"]),
        )
        self.assertEqual(
            {"restoredAdminLogin", "auditVisibility", "webSocketRevoke", "gp05Smoke"},
            set(acceptance["applicationAcceptance"]),
        )
        self.assertEqual(
            "human_review_and_merge_required", acceptance["humanGate"]["requirement"]
        )
        self.assertEqual("pending", acceptance["humanGate"]["status"])

    def test_task_11_actual_evidence_is_sanitized_and_records_verified_results(self):
        manifest = load_json("backup-manifest.json")
        restore = load_json("restore-report.json")
        acceptance = load_json("acceptance.json")

        self.assertEqual(ROW_COUNT_KEYS, set(manifest["rowCounts"]))
        for count in manifest["rowCounts"].values():
            self.assertIs(type(count), int)
            self.assertGreaterEqual(count, 0)
        self.assertEqual("passed", restore["status"])
        self.assertEqual("passed", acceptance["status"])
        self.assertIs(restore["dumpCommitted"], False)
        self.assertIs(acceptance["dumpCommitted"], False)

        self.assertEqual(G4_MERGE_CHECKPOINT_SHA, restore["candidateCommitSha"])
        self.assertEqual(G4_MERGE_CHECKPOINT_SHA, restore["sourceCommitSha"])
        self.assertEqual(G4_MERGE_CHECKPOINT_SHA, acceptance["candidateCommitSha"])
        self.assertEqual(G4_MERGE_CHECKPOINT_SHA, acceptance["sourceCommitSha"])
        self.assertEqual(
            restore["candidateCommitSha"],
            acceptance["candidateCommitSha"],
        )

        for actual in (restore, acceptance):
            self.assertEqual(POST_MERGE_GATE_STATUS, actual["humanGate"]["status"])
            self.assertEqual(
                POST_MERGE_GATE_REQUIREMENT,
                actual["humanGate"]["requirement"],
            )
        self.assertEqual(
            manifest["rowCounts"],
            restore["verification"]["rowCounts"]["expected"],
        )
        self.assertEqual(
            manifest["rowCounts"],
            restore["verification"]["rowCounts"]["observed"],
        )
        for check in restore["verification"]["invariants"]["checks"].values():
            self.assertIs(check, True)
        for section in acceptance["persistence"].values():
            self.assertEqual("passed", section["status"])
        for section in acceptance["applicationAcceptance"].values():
            self.assertEqual("passed", section["status"])
        self.assertEqual(4, acceptance["observations"]["persistedRevokedSessionCount"])
        self.assertEqual(401, acceptance["observations"]["revokedIdentityHttpStatus"])
        self.assertEqual(1008, acceptance["observations"]["oldWebSocketCloseCode"])

        for name in sorted(JSON_EVIDENCE):
            text = (EVIDENCE_ROOT / name).read_text(encoding="utf-8")
            value = load_json(name)
            self.assertIsNone(SECRET_OR_PAYLOAD_PATTERN.search(text), name)
            for child in iter_values(value):
                if isinstance(child, str):
                    self.assertFalse(is_absolute_path(child), f"{name}: {child!r}")
            for key, _ in iter_items(value):
                normalized_key = key.lower().replace("-", "_")
                self.assertFalse(
                    any(part in normalized_key for part in FORBIDDEN_JSON_KEY_PARTS),
                    f"sensitive key {key!r} in {name}",
                )

    def test_task_11_does_not_commit_runtime_or_database_payloads(self):
        forbidden_suffixes = {".dump", ".sql", ".sqlite", ".db", ".bin"}
        files = {path for path in EVIDENCE_ROOT.rglob("*") if path.is_file()}
        self.assertEqual(
            {EVIDENCE_ROOT / path for path in EXPECTED_FILES},
            files,
        )
        self.assertFalse(
            any(path.suffix.lower() in forbidden_suffixes for path in files)
        )

    def test_task_11_screenshots_are_explicit_bounded_png_evidence(self):
        for relative in SANITIZED_SCREENSHOTS:
            screenshot = EVIDENCE_ROOT / relative
            payload = screenshot.read_bytes()
            self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"), relative)
            self.assertGreater(len(payload), 8, relative)
            self.assertLessEqual(len(payload), 5 * 1024 * 1024, relative)

    def test_documentation_links_resolve_and_operator_safety_contract_is_present(self):
        readme = (EVIDENCE_ROOT / "README.md").read_text(encoding="utf-8")
        checklist = (EVIDENCE_ROOT / "RECOVERY_ACCEPTANCE_TEMPLATE.md").read_text(
            encoding="utf-8"
        )
        combined = f"{readme}\n{checklist}"
        self.assertIn(G4_MERGE_CHECKPOINT_SHA, readme)
        self.assertIn("post-merge", readme.lower())
        self.assertIn("G5 Final Code Review / Freeze", readme)
        self.assertNotIn("Human review and human merge remain pending", readme)
        for relative in sorted(JSON_FILES | {"screenshots/"}):
            self.assertIn(relative, combined)
            self.assertTrue((EVIDENCE_ROOT / relative).exists(), relative)
        for required_phrase in (
            "maintenance window",
            "stop platform writers",
            "SUPERSONIC_ALLOW_DB_RESTORE=1",
            "RESTORE_DATABASE_URL",
            "_restore_test",
            "--clean --if-exists --no-owner --no-acl --single-transaction",
            "does not create or drop",
            "does not run Alembic upgrade",
            "Issue #61",
            "Task 11",
            "human merge",
            "G4 PLATFORM COMPLETE",
        ):
            self.assertIn(required_phrase, combined)
        markdown_link = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
        for source in (
            EVIDENCE_ROOT / "README.md",
            EVIDENCE_ROOT / "RECOVERY_ACCEPTANCE_TEMPLATE.md",
        ):
            for target in markdown_link.findall(source.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                self.assertTrue(
                    (source.parent / target.split("#", 1)[0]).exists(), target
                )


if __name__ == "__main__":
    unittest.main()
