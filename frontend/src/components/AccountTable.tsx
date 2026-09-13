import { ArrowDown, ArrowUp, Minus } from "lucide-react"
import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"

import { EmptyState } from "@/components/ui/EmptyState"
import { TrendSparkline } from "@/components/TrendSparkline"
import {
  computeDataCoverage,
  formatCurrency,
  formatDate,
  formatSignalName,
  formatSignalValue,
  MIN_DATA_COVERAGE_DAYS,
  riskTier,
  signalStatus,
  TRACKED_SIGNALS,
} from "@/lib/format"
import { useHealthHistories } from "@/lib/useHealthHistories"
import { useSignalHistories } from "@/lib/useSignalHistories"
import { cn, RISK_STYLES } from "@/lib/utils"
import type { AccountSummary } from "@/types/api"

type SortKey = "name" | "contract_value_monthly" | "composite_score"

const SORTS: Record<SortKey, (a: AccountSummary, b: AccountSummary) => number> = {
  name: (a, b) => a.name.localeCompare(b.name),
  contract_value_monthly: (a, b) => b.contract_value_monthly - a.contract_value_monthly,
  composite_score: (a, b) => (b.composite_score ?? -1) - (a.composite_score ?? -1),
}

const SORT_LABEL: Record<SortKey, string> = {
  name: "Client",
  contract_value_monthly: "Contract value",
  composite_score: "Risk",
}

function TrendArrow({ slope }: { slope: number | null }) {
  if (slope === null || Math.abs(slope) < 0.05) return <Minus className="size-4 text-neutral-500" />
  // Positive trend_slope means risk is increasing period over period (worse).
  return slope > 0 ? <ArrowUp className="size-4 text-risk-ink" /> : <ArrowDown className="size-4 text-healthy-ink" />
}

interface AccountTableProps {
  accounts: AccountSummary[]
  compact?: boolean
}

// The main object of the product — sortable, scannable rows, not a spreadsheet grid.
export function AccountTable({ accounts, compact = false }: AccountTableProps) {
  const navigate = useNavigate()
  const [sort, setSort] = useState<SortKey>("composite_score")
  const [dir, setDir] = useState(1)

  const rows = useMemo(() => [...accounts].sort((a, b) => SORTS[sort](a, b) * dir), [accounts, sort, dir])
  const rowIds = useMemo(() => rows.map((a) => a.id), [rows])
  const { data: histories } = useHealthHistories(rowIds)
  const { data: signalHistories } = useSignalHistories(rowIds)

  const toggle = (key: SortKey) => {
    if (sort === key) setDir(-dir)
    else {
      setSort(key)
      setDir(1)
    }
  }

  const caret = (key: SortKey) => (sort === key ? (dir === 1 ? "↑" : "↓") : "")

  function SortButton({ sortKey }: { sortKey: SortKey }) {
    const active = sort === sortKey
    return (
      <button
        type="button"
        onClick={() => toggle(sortKey)}
        className={cn(
          "border border-divider px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-[0.05em] transition-colors duration-150",
          active ? "bg-ink text-ground" : "text-neutral-700 hover:bg-ink/[0.06]",
        )}
      >
        {SORT_LABEL[sortKey]} {caret(sortKey)}
      </button>
    )
  }

  if (!rows.length) return <EmptyState title="No clients match" body="Clear the search or switch the status filter." />

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-extrabold uppercase tracking-[0.05em] text-neutral-500">Sort by</span>
        <SortButton sortKey="composite_score" />
        <SortButton sortKey="name" />
        <SortButton sortKey="contract_value_monthly" />
      </div>

      <div className="border-t-2 border-divider">
        {rows.map((a, i) => {
          const tier = riskTier(a.composite_score)
          const style = RISK_STYLES[tier]
          const signalHistory = signalHistories[a.id]
          const latestSignals = signalHistory?.[signalHistory.length - 1]
          const concerningSignals = latestSignals
            ? TRACKED_SIGNALS.map((signal) => ({
                signal,
                value: latestSignals[signal] as number,
                status: signalStatus(signal, latestSignals[signal] as number, signalHistory.map((h) => h[signal] as number)),
              })).filter((s) => s.status !== "good")
            : []
          // Only flag "insufficient data" once we have real evidence — composite_score===null is known synchronously, a short history isn't until that fetch resolves.
          const coverage = signalHistory ? computeDataCoverage(signalHistory) : null
          const insufficientData = a.composite_score === null || (coverage !== null && !coverage.isSufficient)
          return (
            <div
              key={a.id}
              onClick={() => navigate(`/accounts/${a.id}`)}
              tabIndex={0}
              role="button"
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault()
                  navigate(`/accounts/${a.id}`)
                }
              }}
              style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
              className={cn(
                "animate-[row-in_280ms_cubic-bezier(0.16,1,0.3,1)_backwards] flex cursor-pointer items-center gap-3 border-b border-l-[3px] border-b-divider py-4 pl-4 pr-3 outline-offset-[-2px] transition-colors duration-150 hover:bg-ink/[0.05] sm:gap-5",
                style.borderLeft,
                style.row,
              )}
            >
              <div className="flex flex-none items-center gap-2.5">
                {!insufficientData && tier === "risk" && (
                  <span className="relative flex size-2.5 flex-none" aria-hidden="true">
                    <span className="absolute inset-0 animate-ping rounded-full bg-risk opacity-75" />
                    <span className="relative size-2.5 rounded-full bg-risk" />
                  </span>
                )}
                <span
                  className={cn(
                    "w-[1.4em] text-right text-[clamp(32px,4vw,44px)] font-extrabold leading-none tabular-nums",
                    insufficientData ? "text-neutral-400" : style.text,
                  )}
                >
                  {insufficientData ? "—" : a.composite_score!.toFixed(0)}
                </span>
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2.5">
                  <span className={cn("min-w-0 truncate text-[17.5px] font-extrabold tracking-[-0.01em]", insufficientData ? "text-ink" : style.text)}>
                    {a.name}
                  </span>
                  <span className="flex-none text-[12px] tabular-nums text-neutral-600">{formatCurrency(a.contract_value_monthly)}/mo</span>
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2.5 gap-y-1">
                  {insufficientData ? (
                    <span className="text-[11px] font-semibold text-neutral-500">
                      Insufficient data{coverage ? ` — ${coverage.days} of ${MIN_DATA_COVERAGE_DAYS} days` : ""}
                    </span>
                  ) : (
                    concerningSignals.map(({ signal, value }) => (
                      <span key={signal} className="text-[11px] font-semibold tabular-nums text-neutral-600">
                        {formatSignalName(signal)} {formatSignalValue(signal, value)}
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div className="flex-none">
                {(histories[a.id]?.length ?? 0) >= 2 ? <TrendSparkline history={histories[a.id]} /> : <TrendArrow slope={a.trend_slope} />}
              </div>

              {!compact && (
                <div className="hidden w-[92px] flex-none text-right text-[11px] text-neutral-700 md:block">
                  {a.health_computed_at ? formatDate(a.health_computed_at) : "Never scored"}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
