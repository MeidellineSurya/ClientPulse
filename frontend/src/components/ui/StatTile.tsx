import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

interface StatTileProps {
  label: string
  value: ReactNode
  sub?: ReactNode
  accent?: boolean
  className?: string
}

// One cell of the ruled metric strip. Never a floating card — the grid does the work.
export function StatTile({ label, value, sub, accent, className }: StatTileProps) {
  return (
    <div className={cn("border-r border-divider px-6 py-4 last:border-r-0", className)}>
      <div className="kicker">{label}</div>
      <div className={cn("mt-1 text-[26px] font-extrabold tracking-[-0.03em]", accent && "text-accent-700")}>{value}</div>
      {sub && <div className="text-[12px] text-neutral-700">{sub}</div>}
    </div>
  )
}
