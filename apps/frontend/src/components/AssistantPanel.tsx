import { Bot, FileText, Mic2, Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { TripRecord } from '../types'

interface Report {
  provider: string
  risk_explanation: string
  trip_report: string
}

export function AssistantPanel() {
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(false)

  const generate = async () => {
    setLoading(true)
    try {
      const tripResponse = await fetch('/api/trips/demo')
      const trip = (await tripResponse.json()) as TripRecord
      const response = await fetch('/api/report/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trip }),
      })
      setReport((await response.json()) as Report)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="panel p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-cyan-400/10 p-2 text-cyan-300"><Bot size={20} /></div>
          <div>
            <p className="eyebrow">Mock LLM</p>
            <h2 className="font-semibold text-white">通勤助手</h2>
          </div>
        </div>
        <span className="rounded-full border border-cyan-300/20 bg-cyan-300/5 px-2 py-1 text-[10px] text-cyan-200">离线可用</span>
      </div>
      <p className="mb-4 min-h-16 text-sm leading-6 text-slate-400">
        {report?.risk_explanation ?? '助手仅解释结构化风险事件，不直接控制车辆，也不提供真实驾驶安全决策。'}
      </p>
      {report && <p className="mb-4 rounded-xl bg-white/[0.035] p-3 text-xs leading-5 text-slate-300">{report.trip_report}</p>}
      <div className="grid grid-cols-2 gap-3">
        <button className="secondary-button" disabled title="语音输入将在P1阶段接入"><Mic2 size={15} /> 语音询问</button>
        <button className="primary-button" onClick={generate} disabled={loading}>
          {loading ? <Sparkles size={15} className="animate-spin" /> : <FileText size={15} />}
          {loading ? '生成中' : '生成报告'}
        </button>
      </div>
    </section>
  )
}

