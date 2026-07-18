import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts.v1 import (
    ENDPOINT_COMMAND_PERMISSIONS,
    CockpitSnapshotV1,
    CommandName,
    ComponentState,
    DataFreshness,
    EndpointId,
    FlowId,
    MessageEnvelopeV1,
    RiskLifecycle,
    RiskSeverity,
    RiskSource,
    RiskType,
    SystemMode,
)

ROOT = Path(__file__).parents[3]
MANIFEST_PATH = ROOT / "contracts" / "gp05" / "v1" / "manifest.json"
SNAPSHOT_PATH = ROOT / "contracts" / "gp05" / "v1" / "example.snapshot.json"


def enum_values(enum_type: type) -> list[str]:
    return [item.value for item in enum_type]


def test_python_enums_and_permissions_match_manifest() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = manifest["enums"]

    assert enum_values(EndpointId) == expected["endpoints"]
    assert enum_values(ComponentState) == expected["componentStates"]
    assert enum_values(SystemMode) == expected["systemModes"]
    assert enum_values(FlowId) == expected["flows"]
    assert enum_values(RiskLifecycle) == expected["riskLifecycles"]
    assert enum_values(RiskSeverity) == expected["riskSeverities"]
    assert enum_values(RiskSource) == expected["riskSources"]
    assert enum_values(RiskType) == expected["riskTypes"]
    assert enum_values(DataFreshness) == expected["dataFreshness"]
    assert enum_values(CommandName) == expected["commandNames"]

    actual_permissions = {
        endpoint.value: sorted(command.value for command in commands)
        for endpoint, commands in ENDPOINT_COMMAND_PERMISSIONS.items()
    }
    expected_permissions = {
        endpoint: sorted(commands)
        for endpoint, commands in manifest["endpointCommandPermissions"].items()
    }
    assert actual_permissions == expected_permissions


def test_snapshot_fixture_round_trips_with_aliases() -> None:
    raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    snapshot = CockpitSnapshotV1.model_validate(raw)
    dumped = snapshot.model_dump(mode="json", by_alias=True)

    assert dumped == raw
    assert snapshot.revision == 42
    assert snapshot.risks[0].lifecycle is RiskLifecycle.ACTIVE


def test_snapshot_rejects_unknown_fields() -> None:
    raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    raw["unknownField"] = True

    with pytest.raises(ValidationError):
        CockpitSnapshotV1.model_validate(raw)


def test_message_union_requires_versioned_envelope_metadata() -> None:
    raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    envelope = {
        "protocolVersion": "gp05.v1",
        "messageId": "5eb3f63d-bebd-4855-98bb-2f706b8aa378",
        "correlationId": "5fcff1d6-1d44-4d23-aad2-967ec94b7052",
        "timestamp": "2026-07-17T08:36:23Z",
        "source": {"kind": "service", "id": "fastapi"},
        "target": None,
        "kind": "snapshot",
        "payload": raw,
    }

    parsed = TypeAdapter(MessageEnvelopeV1).validate_python(envelope)
    assert parsed.kind == "snapshot"
    assert parsed.protocol_version == "gp05.v1"

    del envelope["correlationId"]
    with pytest.raises(ValidationError):
        TypeAdapter(MessageEnvelopeV1).validate_python(envelope)
