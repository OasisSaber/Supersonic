import { RouteOff } from 'lucide-react'
import { CockpitScreen } from './components/CockpitScreen'
import { ENDPOINTS, type EndpointId } from './contracts/gp05-v1'
import { useCockpitSnapshot } from './lib/useCockpitSnapshot'
import { PlatformConsole } from './platform/PlatformConsole'
import { useCockpitStore } from './stores/cockpit'

function endpointFromPath(pathname: string): EndpointId | null {
  const normalized = pathname.endsWith('/') && pathname.length > 1
    ? pathname.slice(0, -1)
    : pathname
  if (!normalized.startsWith('/')) return null

  const candidate = normalized.slice(1)
  if (candidate.includes('/')) return null
  return ENDPOINTS.includes(candidate as EndpointId) ? (candidate as EndpointId) : null
}

function CockpitApp({ endpoint }: { endpoint: EndpointId }) {
  useCockpitSnapshot(endpoint)
  const { connection, snapshot } = useCockpitStore()

  return (
    <div className="sp-app-root" data-theme={snapshot?.theme ?? 'night'}>
      <CockpitScreen endpoint={endpoint} snapshot={snapshot} connection={connection} />
    </div>
  )
}

function InvalidCockpitRoute({ pathname }: { pathname: string }) {
  return (
    <div className="sp-app-root" data-theme="night">
      <main className="sp-route-error">
        <section className="sp-route-error__panel" role="alert">
          <RouteOff size={34} strokeWidth={1.5} aria-hidden="true" />
          <p className="sp-eyebrow">Cockpit route boundary</p>
          <h1>未找到座舱端点</h1>
          <p>仅六个已声明的座舱路径可以启动权威 snapshot 连接。</p>
          <code>{pathname}</code>
        </section>
      </main>
    </div>
  )
}

function isPlatformPath(pathname: string): boolean {
  return pathname === '/platform' || pathname.startsWith('/platform/')
}

export default function App() {
  const { pathname } = window.location
  if (isPlatformPath(pathname)) return <PlatformConsole />

  const endpoint = endpointFromPath(pathname)
  return endpoint
    ? <CockpitApp endpoint={endpoint} />
    : <InvalidCockpitRoute pathname={pathname} />
}
