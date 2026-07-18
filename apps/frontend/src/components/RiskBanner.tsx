import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react'
import type { RiskEvent } from '../types'

const styles = {
  low: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100',
  medium: 'border-amber-400/45 bg-amber-400/15 text-amber-100',
  high: 'border-rose-400/60 bg-rose-500/20 text-rose-50 shadow-[0_0_50px_rgba(244,63,94,.18)]',
}

export function RiskBanner({ risk }: { risk?: RiskEvent }) {
  const level = risk?.level ?? 'low'
  const Icon = level === 'high' ? ShieldAlert : level === 'medium' ? AlertTriangle : CheckCircle2
  return (
    <div className={`flex items-center gap-4 rounded-2xl border px-5 py-4 transition-all duration-500 ${styles[level]}`}>
      <Icon className={level === 'high' ? 'animate-pulse' : ''} />
      <div className="min-w-0 flex-1">
        <p className="text-[10px] uppercase tracking-[0.28em] opacity-65">Risk fusion engine</p>
        <p className="truncate text-base font-semibold">{risk?.message ?? '当前通勤状态稳定'}</p>
      </div>
      <span className="rounded-full border border-current/25 px-3 py-1 text-xs font-bold uppercase">{level}</span>
    </div>
  )
}

