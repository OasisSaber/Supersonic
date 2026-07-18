import { ScanLine, UserRoundSearch } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { SimulationFrame } from '../types'

export function RoadView({ frame }: { frame: SimulationFrame | null }) {
  const road = frame?.sensor.road
  const [videoUrl, setVideoUrl] = useState<string | null>(null)

  useEffect(() => () => {
    if (videoUrl) URL.revokeObjectURL(videoUrl)
  }, [videoUrl])

  const selectVideo = (file?: File) => {
    if (!file) return
    setVideoUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous)
      return URL.createObjectURL(file)
    })
  }

  return (
    <section className="panel relative min-h-[300px] overflow-hidden">
      {videoUrl && (
        <video
          className="absolute inset-0 h-full w-full object-cover opacity-60"
          src={videoUrl}
          autoPlay
          muted
          loop
          controls
          aria-label="已导入的本地行车视频"
        />
      )}
      <div className="absolute inset-0 road-gradient" />
      {!videoUrl && (
        <>
          <div className="absolute left-1/2 top-[35%] h-[70%] w-[42%] -translate-x-1/2 perspective-road" />
          <div className="absolute left-1/2 top-[50%] h-32 w-px -translate-x-1/2 bg-white/60 shadow-[0_0_14px_white]" />
        </>
      )}
      <div className="absolute inset-x-4 top-4 z-10 flex items-center justify-between text-xs uppercase tracking-[0.2em] text-slate-300">
        <span className="flex items-center gap-2"><ScanLine size={15} /> 本地行车视频 · {videoUrl ? '已导入' : 'Mock'}</span>
        <span className="flex items-center gap-3">
          <label className="cursor-pointer rounded-full border border-white/15 bg-black/30 px-3 py-1 tracking-normal transition hover:border-cyan-300/50 hover:text-cyan-200">
            导入视频
            <input
              className="sr-only"
              type="file"
              accept="video/*"
              aria-label="导入本地行车视频"
              onChange={(event) => selectVideo(event.target.files?.[0])}
            />
          </label>
          {frame ? `${frame.sensor.timestamp.toFixed(1)} s` : '等待数据'}
        </span>
      </div>
      <div className="absolute left-[18%] top-[42%] rounded border border-cyan-300/80 px-3 py-5 text-[10px] text-cyan-200">
        VEHICLE · {road?.vehicle_count ?? 0}
      </div>
      {road?.pedestrian_detected && (
        <div className="absolute right-[24%] top-[38%] animate-pulse rounded border-2 border-rose-400 bg-rose-500/15 px-3 py-6 text-xs font-semibold text-rose-200 shadow-[0_0_30px_rgba(244,63,94,.35)]">
          PEDESTRIAN
        </div>
      )}
      <div className="absolute bottom-4 left-4 right-4 z-10 flex items-end justify-between">
        <div>
          <p className="text-xs text-slate-400">基础车道检测</p>
          <p className={road?.lane_departure ? 'text-amber-300' : 'text-emerald-300'}>
            {road?.lane_departure ? '检测到偏离趋势' : '车道保持稳定'}
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-black/35 px-3 py-1.5 text-xs text-slate-300 backdrop-blur">
          <UserRoundSearch size={14} /> 教学验证画面
        </div>
      </div>
    </section>
  )
}
