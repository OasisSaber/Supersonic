import { CockpitScreen } from './components/CockpitScreen'
import { ENDPOINTS, type EndpointId } from './contracts/gp05-v1'
import { useCockpitSnapshot } from './lib/useCockpitSnapshot'
import { PlatformConsole } from './platform/PlatformConsole'
import { useCockpitStore } from './stores/cockpit'

function endpointFromPath(): EndpointId {
  const candidate = window.location.pathname.split('/').filter(Boolean).at(-1)
  return ENDPOINTS.includes(candidate as EndpointId) ? (candidate as EndpointId) : 'overview'
}

function CockpitApp() {
  const endpoint = endpointFromPath()
  useCockpitSnapshot(endpoint)
  const { connection, snapshot } = useCockpitStore()

  return (
    <div className="sp-app-root" data-theme={snapshot?.theme ?? 'night'}>
      <CockpitScreen endpoint={endpoint} snapshot={snapshot} connection={connection} />
    </div>
  )
}

export default function App() {
  return window.location.pathname.startsWith('/platform') ? <PlatformConsole /> : <CockpitApp />
}
