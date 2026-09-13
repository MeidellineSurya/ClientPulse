import { ArrowDown, ArrowUp, Minus } from "lucide-react"
import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/ui/EmptyState"
import { TrendSparkline } from "@/components/TrendSparkline"
import { formatCurrency, formatDate, riskTier } from "@/lib/format"
import { useHealthHistories } from "@/lib/useHealthHistories"
import { cn, RISK_STYLES } from "@/lib/utils"
import type { AccountSummary } from "@/types/api"

type SortKey = "name" | "contract_value_monthly" | "composite_score"

const SORTS: Record<SortKey, (a: AccountSummary, b: AccountSummary) => number> = {
  name: (a, b) => a.name.localeCompare(b.name),
  contract_value_monthly: (a, b) => b.contract_value_monthly - a.contract_value_monthly,
  composite_score: (a, b) => (b.composite_score ?? -1) - (a.composite_score ?? -1),
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

// The main object of the product. Sortable, scannable, one row per client.
// `compact` drops the last-scored column for the overview's shortlist.
export function AccountTable({ accounts, compact = false }: AccountTableProps) {
  const navigate = useNavigate()
  const [sort, setSort] = useState<SortKey>("composite_score")
  const [dir, setDir] = useState(1)

  const rows = useMemo(() => [...accounts].sort((a, b) => SORTS[sort](a, b) * dir), [accounts, sort, dir])
  const histories = useHealthHistories(useMemo(() => rows.map((a) => a.id), [rows]))

  const toggle = (key: SortKey) => {
    if (sort === key) setDir(-dir)
    else {
      setSort(key)
      setDir(1)
    }
  }

  const caret = (key: SortKey) => (sort === key ? (dir === 1 ? "↑" : "↓") : "")

  function Th({ sortKey, children, right }: { sortKey?: SortKey; children: React.ReactNode; right?: boolean }) {
    return (
      <th
        onClick={sortKey ? () => toggle(sortKey) : undefined}
        className={cn(
          "border-b-2 border-divider pb-2 text-[11px] font-extrabold uppercase tracking-[0.05em] text-neutral-700",
          right && "text-right",
          sortKey && "cursor-pointer select-none whitespace-nowrap hover:text-accent",
        )}
      >
        {children} {sortKey && caret(sortKey)}
      </th>
    )
  }

  if (!rows.length) return <EmptyState title="No clients match" body="Clear the search or switch the status filter." />

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-left text-[13px]">
        <thead>
          <tr>
            <Th sortKey="name">Client</Th>
            <Th sortKey="contract_value_monthly" right>
              Contract value
            </Th>
            <Th sortKey="composite_score" right>
              Risk
            </Th>
            <Th>Status</Th>
            <Th>Trend</Th>
            {!compact && <Th right>Last scored</Th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => {
            const tier = riskTier(a.composite_score)
            const style = RISK_STYLES[tier]
            return (
              <tr
                key={a.id}
                onClick={() => navigate(`/accounts/${a.id}`)}
                className={cn("cursor-pointer border-b border-divider hover:bg-ink/[0.05]", style.row)}
              >
                <td className={cn("border-l-[3px] py-3 pl-3", style.border)}>
                  <div className="text-[14px] font-extrabold">{a.name}</div>
                </td>
                <td className="py-3 text-right tabular-nums">{formatCurrency(a.contract_value_monthly)}/mo</td>
                <td className={cn("py-3 text-right text-[17px] font-extrabold", style.text)}>
                  {a.composite_score !== null ? a.composite_score.toFixed(0) : "—"}
                </td>
                <td className="py-3">
                  <Badge tier={tier}>{tier === "risk" ? "At risk" : tier === "unscored" ? "Unscored" : tier === "watch" ? "Watch" : "Healthy"}</Badge>
                </td>
                <td className="py-3">
                  {(histories[a.id]?.length ?? 0) >= 2 ? (
                    <TrendSparkline history={histories[a.id]} />
                  ) : (
                    <TrendArrow slope={a.trend_slope} />
                  )}
                </td>
                {!compact && (
                  <td className="py-3 text-right text-neutral-700">{a.health_computed_at ? formatDate(a.health_computed_at) : "Never scored"}</td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
