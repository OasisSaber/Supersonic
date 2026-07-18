import manifest from '../../../../contracts/gp05/v1/manifest.json'
import snapshotFixture from '../../../../contracts/gp05/v1/example.snapshot.json'
import { describe, expect, it } from 'vitest'
import { GP05_CANVASES, GP05_COMPONENT_STATES } from '../design/gp05-tokens'
import {
  COMMAND_NAMES,
  COMPONENT_STATES,
  DATA_FRESHNESS,
  ENDPOINT_COMMAND_PERMISSIONS,
  ENDPOINTS,
  FLOWS,
  RISK_LIFECYCLES,
  RISK_SEVERITIES,
  RISK_SOURCES,
  RISK_TYPES,
  SYSTEM_MODES,
  isCockpitSnapshotV1,
  isMessageEnvelopeV1,
} from './gp05-v1'

describe('GP05 v1 cross-layer contract', () => {
  it('matches the canonical enum manifest', () => {
    expect(ENDPOINTS).toEqual(manifest.enums.endpoints)
    expect(COMPONENT_STATES).toEqual(manifest.enums.componentStates)
    expect(SYSTEM_MODES).toEqual(manifest.enums.systemModes)
    expect(FLOWS).toEqual(manifest.enums.flows)
    expect(RISK_LIFECYCLES).toEqual(manifest.enums.riskLifecycles)
    expect(RISK_SEVERITIES).toEqual(manifest.enums.riskSeverities)
    expect(RISK_SOURCES).toEqual(manifest.enums.riskSources)
    expect(RISK_TYPES).toEqual(manifest.enums.riskTypes)
    expect(DATA_FRESHNESS).toEqual(manifest.enums.dataFreshness)
    expect(COMMAND_NAMES).toEqual(manifest.enums.commandNames)
  })

  it('keeps endpoint permissions and logical canvases synchronized', () => {
    for (const endpoint of ENDPOINTS) {
      expect([...ENDPOINT_COMMAND_PERMISSIONS[endpoint]].sort()).toEqual(
        [...manifest.endpointCommandPermissions[endpoint]].sort(),
      )
    }

    expect(GP05_CANVASES).toEqual(manifest.canvases)
    expect(GP05_COMPONENT_STATES).toEqual(manifest.enums.componentStates)
  })

  it('accepts the canonical snapshot and rejects obvious invalid data', () => {
    expect(isCockpitSnapshotV1(snapshotFixture)).toBe(true)
    expect(isCockpitSnapshotV1({ ...snapshotFixture, revision: -1.5 })).toBe(false)
    expect(isCockpitSnapshotV1({ ...snapshotFixture, systemMode: 'unknown' })).toBe(false)
    expect(
      isCockpitSnapshotV1({
        ...snapshotFixture,
        risks: [{ ...snapshotFixture.risks[0], confidence: 1.5 }],
      }),
    ).toBe(false)
  })

  it('requires version, IDs, timestamp and source on every envelope', () => {
    const envelope = {
      protocolVersion: 'gp05.v1',
      messageId: '5eb3f63d-bebd-4855-98bb-2f706b8aa378',
      correlationId: '5fcff1d6-1d44-4d23-aad2-967ec94b7052',
      timestamp: '2026-07-17T08:36:23Z',
      source: { kind: 'service', id: 'fastapi' },
      target: null,
      kind: 'snapshot',
      payload: snapshotFixture,
    }

    expect(isMessageEnvelopeV1(envelope)).toBe(true)
    const missingCorrelation = { ...envelope, correlationId: undefined }
    expect(isMessageEnvelopeV1(missingCorrelation)).toBe(false)
  })
})
