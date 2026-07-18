import { GaugeChart } from 'echarts/charts'
import { init, use as registerEChartsModules } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useRef } from 'react'

registerEChartsModules([GaugeChart, CanvasRenderer])

export function SpeedGauge({ speed }: { speed: number }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = init(ref.current)
    chart.setOption({
      series: [
        {
          type: 'gauge',
          min: 0,
          max: 160,
          startAngle: 220,
          endAngle: -40,
          radius: '96%',
          splitNumber: 8,
          axisLine: {
            lineStyle: {
              width: 10,
              color: [
                [0.65, '#43d9b0'],
                [0.85, '#ffb54a'],
                [1, '#ff5964'],
              ],
            },
          },
          pointer: { length: '58%', width: 4, itemStyle: { color: '#f8fbff' } },
          axisTick: { distance: -16, length: 5, lineStyle: { color: '#8fa1bc' } },
          splitLine: { distance: -20, length: 10, lineStyle: { color: '#d7e2f1' } },
          axisLabel: { distance: 16, color: '#77859a', fontSize: 10 },
          detail: {
            valueAnimation: true,
            formatter: '{value}\nkm/h',
            color: '#ffffff',
            fontSize: 24,
            lineHeight: 28,
            offsetCenter: [0, '48%'],
          },
          title: { show: false },
          data: [{ value: Math.round(speed) }],
        },
      ],
    })
    const resize = () => chart.resize()
    window.addEventListener('resize', resize)
    return () => {
      window.removeEventListener('resize', resize)
      chart.dispose()
    }
  }, [speed])

  return <div ref={ref} className="h-56 w-full" aria-label={`当前车速${speed}公里每小时`} />
}
