import type { ReactNode } from "react"

import type { RiskTier } from "@/lib/format"
import { cn, RISK_STYLES } from "@/lib/utils"

interface BadgeProps {
  tier: RiskTier
  children: ReactNode
  className?: string
}

// Risk status pill — Healthy / Watch / At risk. Colour is the only signal carrier.
export function Badge({ tier, children, className }: BadgeProps) {
  const style = RISK_STYLES[tier]
  return (
    <span className={cn("inline-flex px-2 py-[3px] text-[10.5px] font-extrabold uppercase tracking-[0.05em]", style.text, style.bg, className)}>
      {children}
    </span>
  )
}
