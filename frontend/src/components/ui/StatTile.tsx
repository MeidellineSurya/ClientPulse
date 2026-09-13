import type { CSSProperties, ReactNode } from "react"
import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

interface StatTileProps {
  label: string
  value: ReactNode
  sub?: ReactNode
  accent?: boolean
  icon?: LucideIcon
  valueClassName?: string
  className?: string
  style?: CSSProperties
}

// One block of the metric group — a standalone tinted rectangle, not a table cell.
export function StatTile({ label, value, sub, accent, icon: Icon, valueClassName, className, style }: StatTileProps) {
  return (
    <div style={style} className={cn("animate-[row-in_320ms_cubic-bezier(0.16,1,0.3,1)_backwards] bg-surface px-4 py-5 sm:px-6", className)}>
      <div className="flex items-center gap-2 kicker">
        {Icon && <Icon size={15} strokeWidth={2.4} />}
        {label}
      </div>
      <div
        className={cn(
          "mt-2.5 break-words text-[clamp(36px,5.5vw,64px)] font-extrabold tabular-nums leading-none tracking-[-0.03em]",
          accent && "text-accent-700",
          valueClassName,
        )}
      >
        {value}
      </div>
      {sub && <div className="text-[12px] text-neutral-700">{sub}</div>}
    </div>
  )
}
