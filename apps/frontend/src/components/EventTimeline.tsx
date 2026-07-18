import { Clock3 } from 'lucide-react'
import type { RiskEvent } from '../types'

const dot = { low: 'bg-emerald-400', medium: 'bg-amber-400', high: 'bg-rose-400' }

export function EventTimeline({ events }: { events: RiskEvent[] }) {
  return (
    <section className="panel p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="eyebrow">Event stream</p>
          <h2 className="font-semibold text-white">风险事件时间线</h2>
        </div>
        <Clock3 size={18} className="text-slate-500" />
      </div>
      <div className="space-y-3">
        {events.length === 0 && <p className="py-6 text-center text-sm text-slate-500">等待风险事件</p>}
        {events.map((event, index) => (
          <button key={`${event.timestamp}-${index}`} className="group flex w-full items-start gap-3 rounded-xl p-2 text-left transition hover:bg-white/5">
            <span className={`mt-1.5 h-2.5 w-2.5 rounded-full ${dot[event.level]}`} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm text-slate-200">{event.message}</span>
              <span className="text-[11px] text-slate-500">{event.timestamp.toFixed(1)} 秒 · 点击可定位（下一阶段）</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}

