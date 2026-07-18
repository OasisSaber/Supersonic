import { Eye, Moon, UserCheck } from 'lucide-react'
import type { DriverState } from '../types'

export function DriverMonitor({ driver }: { driver?: DriverState }) {
  const distracted = driver?.distracted ?? false
  return (
    <section className="panel p-5">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="eyebrow">Cabin camera</p>
          <h2 className="font-semibold text-white">驾驶员状态</h2>
        </div>
        <div className={`status-dot ${distracted ? 'bg-rose-400' : 'bg-emerald-400'}`} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Status icon={<Eye size={18} />} label="视线" value={distracted ? '偏移' : '正常'} alert={distracted} />
        <Status icon={<Moon size={18} />} label="疲劳" value={driver?.fatigue_level ?? 'low'} alert={driver?.fatigue_level === 'high'} />
        <Status icon={<UserCheck size={18} />} label="闭眼" value={`${(driver?.eyes_closed_duration ?? 0).toFixed(1)}s`} alert={(driver?.eyes_closed_duration ?? 0) > 1} />
      </div>
    </section>
  )
}

function Status({ icon, label, value, alert }: { icon: React.ReactNode; label: string; value: string; alert: boolean }) {
  return (
    <div className={`rounded-xl border p-3 ${alert ? 'border-rose-400/40 bg-rose-400/10' : 'border-white/5 bg-white/[0.025]'}`}>
      <div className="mb-2 text-slate-400">{icon}</div>
      <p className="text-[10px] text-slate-500">{label}</p>
      <p className={`text-sm font-semibold ${alert ? 'text-rose-200' : 'text-slate-100'}`}>{value}</p>
    </div>
  )
}

