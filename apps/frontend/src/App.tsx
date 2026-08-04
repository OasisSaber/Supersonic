import { CockpitScreen } from './components/CockpitScreen'
import { ENDPOINTS, type EndpointId } from './contracts/gp05-v1'
import { useCockpitSnapshot } from './lib/useCockpitSnapshot'
import { useCockpitStore } from './stores/cockpit'

function endpointFromPath(): EndpointId {
  const candidate = window.location.pathname.split('/').filter(Boolean).at(-1)
  return ENDPOINTS.includes(candidate as EndpointId) ? (candidate as EndpointId) : 'overview'
}

export default function App() {
  const endpoint = endpointFromPath()
  useCockpitSnapshot(endpoint)
  const { connection, snapshot } = useCockpitStore()

  return (
    <div className="sp-app-root" data-theme={snapshot?.theme ?? 'night'}>
      <CockpitScreen endpoint={endpoint} snapshot={snapshot} connection={connection} />
    </div>
  )
}
