from __future__ import annotations

import json
import os
import stat
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

from app.platform.audit_fallback import (
    AuditFallbackBusy,
    AuditFallbackFormatError,
    AuditFallbackFull,
    JsonlAuditFallback,
)
from app.platform.models import AuditDelivery, AuditEvent, AuditResult, Role

EVENT_ID = "11111111-1111-4111-8111-111111111111"
EVENT_TIME = datetime(2026, 8, 13, 12, tzinfo=UTC)


def event(*, occurred_at: datetime = EVENT_TIME) -> AuditEvent:
    return AuditEvent(
        id=EVENT_ID,
        occurred_at=occurred_at,
        action="cockpit.command",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
        actor_role=Role.OPERATOR,
        parameters={
            "api_key": "must-not-write",
            "destinationName": "private location",
            "command": "set_theme",
        },
    )


class _PrivateDatetime(datetime):
    def isoformat(self, sep: str = "T", timespec: str = "auto") -> str:
        return "PRIVATE-occurred-at-value"


class _PrivateEnumLike:
    def __init__(self, value: str) -> None:
        self.value = value


class _Masquerade(str):
    def __new__(
        cls,
        private_value: str,
        allowed_value: str,
    ) -> _Masquerade:
        instance = super().__new__(cls, private_value)
        instance._allowed_value = allowed_value
        return instance

    def __hash__(self) -> int:
        return hash(self._allowed_value)

    def __eq__(self, other: object) -> bool:
        return other == self._allowed_value


class _ExplosiveParameterDict(dict[str, object]):
    def values(self):  # type: ignore[override]
        raise AssertionError("fallback must not call untrusted values()")


def test_fallback_serializes_sanitized_event_with_fallback_delivery(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    persisted = fallback.append(event())
    line = json.loads(path.read_text(encoding="utf-8"))

    assert persisted.delivery is AuditDelivery.FALLBACK
    assert line["schemaVersion"] == 1
    assert line["delivery"] == "fallback"
    assert line["parameters"] == {
        "api_key": "[redacted]",
        "destinationName": "[redacted]",
        "command": "set_theme",
    }
    assert fallback.load_events() == [persisted]


def test_fallback_capacity_error_preserves_existing_file(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    original = "{\"already\":\"stored\"}\n"
    path.write_text(original, encoding="utf-8")
    fallback = JsonlAuditFallback(path, max_bytes=len(original.encode("utf-8")))

    with pytest.raises(AuditFallbackFull, match="maximum size"):
        fallback.append(event())

    assert path.read_text(encoding="utf-8") == original


def test_fallback_reader_rejects_a_source_larger_than_its_configured_cap(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(AuditFallbackFull, match="maximum size"):
        JsonlAuditFallback(path, max_bytes=2).load_events()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not NTFS ACLs")
def test_fallback_hardens_an_existing_file_to_owner_only_permissions(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    path.write_text("", encoding="utf-8")
    path.chmod(0o644)

    JsonlAuditFallback(path).append(event())

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not NTFS ACLs")
def test_fallback_requests_owner_only_modes_for_each_new_parent(tmp_path) -> None:
    parent = tmp_path / "restricted" / "nested"
    path = parent / "audit-fallback.jsonl"

    JsonlAuditFallback(path).append(event())

    assert stat.S_IMODE((tmp_path / "restricted").stat().st_mode) == 0o700
    assert stat.S_IMODE(parent.stat().st_mode) == 0o700


def test_fallback_rejects_a_second_cooperative_writer_while_locked(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    other_writer = JsonlAuditFallback(path)

    with fallback.locked():
        with pytest.raises(AuditFallbackBusy, match="busy"):
            other_writer.append(event())

    assert not path.exists()


@pytest.mark.parametrize(
    "payload",
    [
        "not-json\n",
        '{"schemaVersion":1,"delivery":"primary"}\n',
        '{"schemaVersion":2,"delivery":"fallback"}\n',
    ],
)
def test_fallback_reader_rejects_malformed_or_unexpected_records(
    tmp_path,
    payload: str,
) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(AuditFallbackFormatError):
        JsonlAuditFallback(path).load_events()


def test_fallback_rejects_naive_audit_event_before_writing(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    with pytest.raises(AuditFallbackFormatError, match="timezone-aware"):
        fallback.append(event(occurred_at=datetime(2026, 8, 13, 12)))

    assert not path.exists()


@pytest.mark.parametrize(
    ("field_name", "unsafe_value", "message"),
    [
        (
            "occurred_at",
            cast(datetime, _PrivateDatetime(2026, 8, 13, 12, tzinfo=UTC)),
            "occurred_at must be a datetime",
        ),
        (
            "result",
            cast(AuditResult, _PrivateEnumLike("PRIVATE-result-value")),
            "result must be an AuditResult",
        ),
        (
            "delivery",
            cast(AuditDelivery, _PrivateEnumLike("PRIVATE-delivery-value")),
            "delivery must be an AuditDelivery",
        ),
        (
            "actor_role",
            cast(Role, _PrivateEnumLike("PRIVATE-role-value")),
            "actor_role must be a Role or None",
        ),
    ],
)
def test_fallback_rejects_custom_runtime_values_before_writing(
    tmp_path,
    field_name: str,
    unsafe_value: object,
    message: str,
) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    with pytest.raises(AuditFallbackFormatError, match=message):
        fallback.append(replace(event(), **{field_name: unsafe_value}))

    assert not path.exists()


@pytest.mark.parametrize(
    ("field_name", "allowed_value"),
    [
        ("action", "cockpit.command"),
        ("endpoint", "center"),
        ("command_name", "set_theme"),
        ("target_type", "risk_event"),
        ("error_code", "risk_not_found"),
        ("source_type", "local_hmi"),
    ],
)
def test_fallback_rejects_str_subclass_metadata_before_writing(
    tmp_path,
    field_name: str,
    allowed_value: str,
) -> None:
    private_value = f"PRIVATE-{field_name}-value"
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    with pytest.raises(AuditFallbackFormatError, match="must be a non-empty string"):
        fallback.append(
            replace(event(), **{field_name: _Masquerade(private_value, allowed_value)})
        )

    assert not path.exists()


def test_fallback_redacts_a_masquerading_safe_parameter_value(tmp_path) -> None:
    private_value = "PRIVATE-parameter-value"
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    persisted = fallback.append(
        replace(
            event(),
            parameters={"command": _Masquerade(private_value, "set_theme")},
        )
    )

    assert persisted.parameters == {"command": "[redacted]"}
    assert private_value not in path.read_text(encoding="utf-8")


def test_fallback_drops_a_masquerading_safe_parameter_key(tmp_path) -> None:
    private_key = "PRIVATE-parameter-key"
    private_value = "PRIVATE-parameter-value"
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    persisted = fallback.append(
        replace(
            event(),
            parameters={
                _Masquerade(private_key, "command"): _Masquerade(
                    private_value,
                    "set_theme",
                )
            },
        )
    )

    assert persisted.parameters == {}
    persisted_text = path.read_text(encoding="utf-8")
    assert private_key not in persisted_text
    assert private_value not in persisted_text


def test_fallback_drops_an_untrusted_parameter_container_without_calling_it(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    persisted = fallback.append(
        replace(event(), parameters=cast(dict[str, object], _ExplosiveParameterDict()))
    )

    assert persisted.parameters == {}
    assert fallback.load_events()[0].parameters == {}


def test_fallback_rejects_non_finite_json_values_before_writing(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    with pytest.raises(AuditFallbackFormatError, match="JSON-compatible"):
        fallback.append(replace(event(), parameters={"riskScore": float("nan")}))

    assert not path.exists()


def test_fallback_reader_rejects_nonstandard_json_numbers(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    fallback.append(event())
    payload = path.read_text(encoding="utf-8").replace('"set_theme"', "NaN")
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(AuditFallbackFormatError, match="not valid JSON"):
        fallback.load_events()


def test_fallback_reader_re_sanitizes_a_tampered_parameter_payload(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    fallback.append(event())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["parameters"] = {"raw_token": "must-not-return"}
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    loaded = fallback.load_events()

    assert loaded[0].parameters == {"raw_token": "[redacted]"}


@pytest.mark.parametrize(
    ("key", "unsafe_value"),
    [
        ("database_dsn", "postgresql+psycopg://audit:secret@db.example.test/audit"),
        ("sql_error", "SELECT * FROM private_audit_events"),
        ("command", "Ab9cDe0fGh1iJk2Lm3No4Pq5Rs6Tu7Vw"),
    ],
)
def test_fallback_redacts_sensitive_parameter_values_even_with_unknown_keys(
    tmp_path,
    key: str,
    unsafe_value: str,
) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    fallback.append(replace(event(), parameters={key: unsafe_value}))

    assert unsafe_value not in path.read_text(encoding="utf-8")
    assert fallback.load_events()[0].parameters == {key: "[redacted]"}


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "postgresql+psycopg://audit:secret@db.example.test/audit",
        "SELECT * FROM private_audit_events",
        "C:/private/student/photo.png",
    ],
)
def test_fallback_redacts_private_parameter_values_with_neutral_keys(
    tmp_path,
    unsafe_value: str,
) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    fallback.append(replace(event(), parameters={"detail": unsafe_value}))

    assert unsafe_value not in path.read_text(encoding="utf-8")
    assert fallback.load_events()[0].parameters == {}


def test_fallback_redacts_an_unknown_parameter_object_without_rendering_it(tmp_path) -> None:
    class SecretBearingObject:
        def __str__(self) -> str:
            return "postgresql+psycopg://audit:secret@db.example.test/audit"

    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    fallback.append(replace(event(), parameters={"detail": SecretBearingObject()}))

    assert "postgresql+psycopg://" not in path.read_text(encoding="utf-8")
    assert fallback.load_events()[0].parameters == {}


def test_fallback_drops_unknown_parameter_keys_and_free_form_text(tmp_path) -> None:
    private_key = "C:/private/student/photo.png"
    private_text = "meet me behind the red building after class"
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    fallback.append(
        replace(
            event(),
            parameters={
                "command": "set_theme",
                "request": {"label": "visible", "detail": private_text},
                private_key: "visible",
            },
        )
    )

    persisted = path.read_text(encoding="utf-8")
    assert private_key not in persisted
    assert private_text not in persisted
    assert fallback.load_events()[0].parameters == {
        "command": "set_theme",
    }


def test_fallback_keeps_known_parameters_after_unknown_noise(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    private_text = "meet me behind the red building after class"
    parameters: dict[str, object] = {
        f"unknown_{index}": private_text for index in range(8)
    }
    parameters.update(
        {
            "command": "set_theme",
            "eventId": f"simulated-takeover-{EVENT_ID}",
            "theme": "night",
        }
    )

    fallback.append(replace(event(), parameters=parameters))

    persisted = path.read_text(encoding="utf-8")
    assert private_text not in persisted
    assert fallback.load_events()[0].parameters == {
        "command": "set_theme",
        "eventId": f"simulated-takeover-{EVENT_ID}",
        "theme": "night",
    }


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        (
            {
                "attempt": 2,
                "command": "set_theme",
                "count": 5,
                "eventId": f"simulated-takeover-{EVENT_ID}",
                "mode": "takeover",
                "privacyEnabled": True,
                "state": "playing",
                "status": "ready",
                "temperatureC": 22.5,
                "theme": "night",
            },
            {
                "attempt": 2,
                "command": "set_theme",
                "count": 5,
                "eventId": f"simulated-takeover-{EVENT_ID}",
                "mode": "takeover",
                "privacyEnabled": True,
                "state": "playing",
                "status": "ready",
                "temperatureC": 22.5,
                "theme": "night",
            },
        ),
        (
            {
                "attempt": -1,
                "command": "Ab9cDe0fGh1iJk2Lm3No4Pq5Rs6Tu7Vw",
                "eventId": "private path / home",
                "mode": "custom",
                "privacyEnabled": "true",
                "temperatureC": 201,
            },
            {
                "attempt": "[redacted]",
                "command": "[redacted]",
                "eventId": "[redacted]",
                "mode": "[redacted]",
                "privacyEnabled": "[redacted]",
                "temperatureC": "[redacted]",
            },
        ),
        (
            {"eventId": "risk-private-home"},
            {"eventId": "[redacted]"},
        ),
    ],
)
def test_fallback_keeps_only_typed_safe_audit_parameters(
    tmp_path,
    parameters: dict[str, object],
    expected: dict[str, object],
) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    persisted = fallback.append(replace(event(), parameters=parameters))

    assert persisted.parameters == expected
    assert fallback.load_events()[0].parameters == expected


def test_fallback_keeps_only_typed_safe_metadata(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    safe_metadata = {
        "action": "risk.detected",
        "endpoint": "center",
        "cockpit_session_id": "22222222-2222-4222-8222-222222222222",
        "command_name": "acknowledge_risk",
        "correlation_id": "33333333-3333-4333-8333-333333333333",
        "target_type": "risk_event",
        "target_id": f"simulated-takeover-{EVENT_ID}",
        "error_code": "risk_not_found",
        "source_type": "local_hmi",
    }

    persisted = fallback.append(replace(event(), **safe_metadata))
    payload = json.loads(path.read_text(encoding="utf-8"))

    for field_name, expected in safe_metadata.items():
        assert getattr(persisted, field_name) == expected
    assert payload == {
        **payload,
        "action": "risk.detected",
        "endpoint": "center",
        "cockpitSessionId": "22222222-2222-4222-8222-222222222222",
        "commandName": "acknowledge_risk",
        "correlationId": "33333333-3333-4333-8333-333333333333",
        "targetType": "risk_event",
        "targetId": f"simulated-takeover-{EVENT_ID}",
        "errorCode": "risk_not_found",
        "sourceType": "local_hmi",
    }


@pytest.mark.parametrize(
    "field_name",
    [
        "action",
        "endpoint",
        "cockpit_session_id",
        "command_name",
        "correlation_id",
        "target_type",
        "target_id",
        "error_code",
        "source_type",
    ],
)
def test_fallback_redacts_uncontrolled_metadata_before_writing(
    tmp_path,
    field_name: str,
) -> None:
    unsafe_value = "meet-alice-at-home"
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)

    persisted = fallback.append(replace(event(), **{field_name: unsafe_value}))

    assert unsafe_value not in path.read_text(encoding="utf-8")
    assert getattr(persisted, field_name) == "[redacted]"
    assert getattr(fallback.load_events()[0], field_name) == "[redacted]"


def test_fallback_reader_redacts_unsafe_tampered_metadata(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    fallback.append(event())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["targetId"] = "C:/private/student/photo.png"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    loaded = fallback.load_events()

    assert loaded[0].target_id == "[redacted]"


def test_fallback_rejects_invalid_optional_actor_uuid_before_writing(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    invalid = AuditEvent(
        id=EVENT_ID,
        occurred_at=EVENT_TIME,
        action="cockpit.command",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
        actor_user_id="not-a-uuid",
    )

    with pytest.raises(AuditFallbackFormatError, match="actor_user_id must be a valid UUID"):
        fallback.append(invalid)

    assert not path.exists()


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("action", "a" * 129, "action must be at most 128 characters"),
        ("source_type", "s" * 33, "source_type must be at most 32 characters"),
        ("command_name", "c" * 65, "command_name must be at most 64 characters"),
    ],
)
def test_fallback_rejects_values_that_the_postgresql_schema_cannot_store(
    tmp_path,
    field_name: str,
    value: str,
    message: str,
) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    values = {field_name: value}

    with pytest.raises(AuditFallbackFormatError, match=message):
        fallback.append(replace(event(), **values))

    assert not path.exists()


def test_fallback_reader_rejects_a_missing_versioned_schema_field(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    fallback.append(event())
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["endpoint"]
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(AuditFallbackFormatError, match="unexpected field set"):
        fallback.load_events()


def test_fallback_reader_rejects_tampered_metadata_that_exceeds_schema_limits(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    fallback.append(event())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["action"] = "a" * 129
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(AuditFallbackFormatError, match="action must be at most 128 characters"):
        fallback.load_events()


def test_fallback_reader_rejects_a_boolean_schema_version(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    fallback.append(event())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schemaVersion"] = True
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(AuditFallbackFormatError, match="unsupported schema version"):
        fallback.load_events()


def test_fallback_reader_rejects_non_string_enum_values_as_format_errors(tmp_path) -> None:
    path = tmp_path / "audit-fallback.jsonl"
    fallback = JsonlAuditFallback(path)
    fallback.append(event())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["result"] = []
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(AuditFallbackFormatError, match="result is invalid"):
        fallback.load_events()
