import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts"

import { HEX } from "@/lib/utils"
import type { HealthScorePoint } from "@/types/api"

interface TrendSparklineProps {
  history: HealthScorePoint[]
}

// 220x34 inline trend of composite risk score. No axes, no tooltip — shape only.
// Colour follows direction: rising risk is bad (red), falling risk is good (green).
export function TrendSparkline({ history }: TrendSparklineProps) {
  const data = history.map((p) => ({ score: p.composite_score }))
  const delta = data[data.length - 1].score - data[0].score
  const stroke = delta > 6 ? HEX.risk : delta > 0 ? HEX.watch : delta < 0 ? HEX.healthy : HEX.unscored

  return (
    <div className="flex items-center gap-3">
      <div className="hidden h-[34px] w-[110px] flex-none sm:block sm:w-[160px] lg:w-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <YAxis hide domain={["dataMin - 2", "dataMax + 2"]} />
            <Line type="monotone" dataKey="score" stroke={stroke} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <span className="text-[12px] font-extrabold tabular-nums" style={{ color: stroke }}>
        {delta > 0 ? "+" : ""}
        {delta.toFixed(0)}
      </span>
    </div>
  )
}
