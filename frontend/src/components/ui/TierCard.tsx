import type { CSSProperties } from "react"
import { CheckCircle2, Eye, TriangleAlert } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"

import { formatCurrency, type RiskTier } from "@/lib/format"
import { useCountUp } from "@/lib/useCountUp"
import { cn, RISK_STYLES } from "@/lib/utils"
import type { AccountSummary } from "@/types/api"

interface TierCardProps {
  tier: Exclude<RiskTier, "unscored">
  label: string
  accounts: AccountSummary[]
  style?: CSSProperties
}

const TIER_ICON = {
  risk: TriangleAlert,
  watch: Eye,
  healthy: CheckCircle2,
} as const

// Color-coded tier count that opens to the accounts behind it, without leaving the page.
export function TierCard({ tier, label, accounts, style }: TierCardProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const tone = RISK_STYLES[tier]
  const countDisplay = useCountUp(accounts.length, 500)
  const Icon = TIER_ICON[tier]

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: PointerEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [open])

  return (
    <div ref={ref} style={style} className="relative animate-[row-in_320ms_cubic-bezier(0.16,1,0.3,1)_backwards]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cn("flex w-full flex-col items-start px-6 py-5 text-left transition duration-150 hover:brightness-[0.97]", tone.bg)}
      >
        <span className={cn("flex items-center gap-2 kicker", tone.text)}>
          <Icon size={15} strokeWidth={2.4} />
          {label}
        </span>
        <span className={cn("mt-2.5 text-[clamp(36px,5.5vw,64px)] font-extrabold leading-none tabular-nums tracking-[-0.03em]", tone.text)}>
          {Math.round(countDisplay)}
        </span>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-10 w-[270px] animate-[row-in_160ms_cubic-bezier(0.16,1,0.3,1)_backwards] border border-divider bg-ground shadow-[0_10px_28px_rgba(32,30,29,0.18)]">
          <div className={cn("border-b border-divider px-4 py-2.5 text-[11px] font-extrabold uppercase tracking-[0.08em]", tone.text)}>
            {label} · {accounts.length}
          </div>
          {accounts.length === 0 ? (
            <p className="px-4 py-4 text-[12.5px] text-neutral-700">No accounts in this tier.</p>
          ) : (
            <ul className="max-h-[240px] overflow-y-auto">
              {accounts.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => navigate(`/accounts/${a.id}`)}
                    className="flex w-full items-center justify-between gap-3 border-b border-divider px-4 py-2.5 text-left text-[13px] font-semibold transition-colors duration-150 last:border-b-0 hover:bg-ink/[0.05]"
                  >
                    <span className="truncate">{a.name}</span>
                    <span className="flex-none text-[11px] font-normal tabular-nums text-neutral-600">{formatCurrency(a.contract_value_monthly)}/mo</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
