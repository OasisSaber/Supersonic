import type { CockpitSnapshotV1, EndpointId } from '../contracts/gp05-v1'
import { screenStateClass } from '../lib/cockpitPresentation'
import { selectPrimaryRisk } from '../lib/riskSelection'
import type { ConnectionState } from '../stores/cockpit'
import { CenterScreen } from './screens/CenterScreen'
import { ClusterScreen } from './screens/ClusterScreen'
import { ControlScreen } from './screens/ControlScreen'
import { HudScreen } from './screens/HudScreen'
import { OverviewScreen } from './screens/OverviewScreen'
import { PassengerScreen } from './screens/PassengerScreen'
import { ScreenShell } from './ui/ScreenShell'

interface CockpitScreenProps {
  connection: ConnectionState
  endpoint: EndpointId
  snapshot: CockpitSnapshotV1 | null
}

export function CockpitScreen({ connection, endpoint, snapshot }: CockpitScreenProps) {
  const activeRisk = selectPrimaryRisk(snapshot?.risks ?? [])

  return (
    <main
      className={`cockpit-screen ${screenStateClass(snapshot)} ${
        activeRisk ? `risk-${activeRisk.severity}` : ''
      }`}
      data-endpoint={endpoint}
    >
      <ScreenShell connection={connection} endpoint={endpoint} snapshot={snapshot}>
        {endpoint === 'cluster' ? <ClusterScreen activeRisk={activeRisk} snapshot={snapshot} /> : null}
        {endpoint === 'hud' ? <HudScreen activeRisk={activeRisk} snapshot={snapshot} /> : null}
        {endpoint === 'center' ? <CenterScreen activeRisk={activeRisk} snapshot={snapshot} /> : null}
        {endpoint === 'passenger' ? <PassengerScreen activeRisk={activeRisk} snapshot={snapshot} /> : null}
        {endpoint === 'overview' ? (
          <OverviewScreen activeRisk={activeRisk} connection={connection} snapshot={snapshot} />
        ) : null}
        {endpoint === 'control' ? <ControlScreen snapshot={snapshot} /> : null}
      </ScreenShell>
    </main>
  )
}
