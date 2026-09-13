import { Activity, ArrowDown, ArrowUp, Bell, ListChecks, Minus, Moon, Sun, Sunrise, TriangleAlert, Users, Wallet } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts"

import { AccountTable } from "@/components/AccountTable"
import { AlertCard } from "@/components/AlertCard"
import { Loading } from "@/components/ui/Loading"
import { StatTile } from "@/components/ui/StatTile"
import { TierCard } from "@/components/ui/TierCard"
import { api, ApiError } from "@/lib/api"
import { formatCurrency, formatSignalName, HIGHER_IS_WORSE, riskTier } from "@/lib/format"
import { useCountUp } from "@/lib/useCountUp"
import { useSignalHistories } from "@/lib/useSignalHistories"
import { cn, HEX } from "@/lib/utils"
import type { Alert, AccountSummary, SignalSnapshot } from "@/types/api"

// No /agency endpoint exists yet — matches the seeded agency.name value but isn't wired to a live response.
const AGENCY_NAME = "StudioCo"

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return { label: "Good morning", icon: Sunrise }
  if (hour < 18) return { label: "Good afternoon", icon: Sun }
  return { label: "Good evening", icon: Moon }
}

const SHORT_SIGNAL_LABEL: Record<string, string> = {
  avg_response_time_hours: "Response time",
  meetings_cancelled: "Cancelled",
  contact_changed: "Contact change",
  invoice_days_late: "Late invoices",
  meetings_scheduled: "Scheduled",
}

// Every signal the scoring engine tracks, in weight order — shown even at 0 so nothing silently drops off the chart.
const ALL_SIGNALS = Object.keys(SHORT_SIGNAL_LABEL)

// contact_changed is a point-in-time flag, not a continuous metric, so it's excluded from trend lines here.
const TREND_SIGNALS: Array<keyof SignalSnapshot> = [
  "avg_response_time_hours",
  "meetings_cancelled",
  "invoice_days_late",
  "meetings_scheduled",
]

type TrendPoint = { period: string; value: number }

function trendDirection(signal: string, series: TrendPoint[]): "worse" | "better" | "flat" | "unknown" {
  if (series.length < 2) return "unknown"
  const values = series.map((p) => p.value)
  const range = Math.max(...values) - Math.min(...values)
  const delta = series[series.length - 1].value - series[0].value
  if (range === 0 || Math.abs(delta) < range * 0.08) return "flat"
  const worse = HIGHER_IS_WORSE[signal] ? delta > 0 : delta < 0
  return worse ? "worse" : "better"
}

export function Portfolio() {
  const navigate = useNavigate()
  const greeting = useMemo(() => getGreeting(), [])
  const GreetingIcon = greeting.icon
  const [accounts, setAccounts] = useState<AccountSummary[] | null>(null)
  const [alerts, setAlerts] = useState<Alert[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const [justUpdatedId, setJustUpdatedId] = useState<string | null>(null)

  useEffect(() => {
    api
      .listAccounts()
      .then(setAccounts)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load accounts"))
    api.listAlerts().then(setAlerts).catch(() => {
      // Non-fatal: the "latest alerts" panel just renders empty if this fails.
    })
  }, [])

  const accountById = useMemo(() => new Map((accounts ?? []).map((a) => [a.id, a])), [accounts])

  async function updateStatus(alert: Alert, nextStatus: Alert["status"]) {
    if (nextStatus === alert.status) return
    setUpdatingId(alert.id)
    try {
      const updated = await api.setAlertStatus(alert.id, nextStatus)
      setAlerts((prev) =>
        prev?.map((a) =>
          a.id === alert.id ? { ...updated, account_name: updated.account_name ?? a.account_name } : a,
        ) ?? null,
      )
      setJustUpdatedId(alert.id)
      window.setTimeout(() => setJustUpdatedId((id) => (id === alert.id ? null : id)), 900)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update alert")
    } finally {
      setUpdatingId(null)
    }
  }

  const atRisk = useMemo(() => accounts?.filter((a) => riskTier(a.composite_score) === "risk") ?? [], [accounts])
  const watch = useMemo(() => accounts?.filter((a) => riskTier(a.composite_score) === "watch") ?? [], [accounts])
  const healthy = useMemo(() => accounts?.filter((a) => riskTier(a.composite_score) === "healthy") ?? [], [accounts])

  const healthyRevenue = useMemo(() => healthy.reduce((sum, a) => sum + a.contract_value_monthly, 0), [healthy])
  const atRiskRevenue = useMemo(() => atRisk.reduce((sum, a) => sum + a.contract_value_monthly, 0), [atRisk])
  const totalMonthlyRevenue = useMemo(() => (accounts ?? []).reduce((sum, a) => sum + a.contract_value_monthly, 0), [accounts])
  const atRiskShare = totalMonthlyRevenue > 0 ? atRiskRevenue / totalMonthlyRevenue : 0
  const shortlist = useMemo(
    () => [...(accounts ?? [])].sort((a, b) => (b.composite_score ?? -1) - (a.composite_score ?? -1)).slice(0, 5),
    [accounts],
  )

  const openAlertsCount = useMemo(() => (alerts ?? []).filter((a) => a.status === "open").length, [alerts])
  const signalCounts = useMemo(() => {
    const counts = new Map<string, number>(ALL_SIGNALS.map((signal) => [signal, 0]))
    for (const alert of alerts ?? []) {
      for (const signal of alert.signals_fired) {
        counts.set(signal, (counts.get(signal) ?? 0) + 1)
      }
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1])
  }, [alerts])
  const maxSignalCount = Math.max(1, signalCounts[0]?.[1] ?? 0)

  const accountIds = useMemo(() => accounts?.map((a) => a.id) ?? [], [accounts])
  const { data: signalHistories, loading: signalHistoriesLoading } = useSignalHistories(accountIds)
  const portfolioSignalTrends = useMemo(() => {
    const byPeriod = new Map<string, Partial<Record<keyof SignalSnapshot, { sum: number; count: number }>>>()
    for (const history of Object.values(signalHistories)) {
      for (const row of history) {
        let bucket = byPeriod.get(row.period_start)
        if (!bucket) {
          bucket = {}
          byPeriod.set(row.period_start, bucket)
        }
        for (const signal of TREND_SIGNALS) {
          const entry = bucket[signal] ?? { sum: 0, count: 0 }
          entry.sum += row[signal] as number
          entry.count += 1
          bucket[signal] = entry
        }
      }
    }
    const periods = [...byPeriod.keys()].sort()
    return TREND_SIGNALS.map((signal) => ({
      signal,
      series: periods.flatMap((period) => {
        const entry = byPeriod.get(period)?.[signal]
        return entry ? [{ period, value: entry.sum / entry.count }] : []
      }),
    }))
  }, [signalHistories])
  const signalCountMap = useMemo(() => new Map<string, number>(signalCounts), [signalCounts])
  const trendMap = useMemo(
    () => new Map<string, (typeof portfolioSignalTrends)[number]>(portfolioSignalTrends.map((t) => [t.signal, t])),
    [portfolioSignalTrends],
  )

  const totalCountDisplay = useCountUp(accounts?.length ?? 0, 500)
  const healthyRevenueDisplay = useCountUp(healthyRevenue, 800)
  const atRiskRevenueDisplay = useCountUp(atRiskRevenue, 800)
  const [barMounted, setBarMounted] = useState(false)
  useEffect(() => {
    const raf = requestAnimationFrame(() => setBarMounted(true))
    return () => cancelAnimationFrame(raf)
  }, [])

  if (error) {
    return <div className="m-10 border border-risk px-4 py-3 text-[13px] text-risk-ink">Couldn't load accounts: {error}</div>
  }

  if (!accounts || !alerts) {
    return (
      <div className="p-10">
        <Loading rows={8} />
      </div>
    )
  }

  return (
    <div>
      <section className="px-10 pb-4 pt-8">
        <div className="flex items-center justify-between gap-4">
          <p className="flex items-center gap-2 text-[17px] font-semibold text-neutral-700">
            <GreetingIcon size={19} strokeWidth={2.2} className="text-accent" />
            {greeting.label}, {AGENCY_NAME}.
          </p>
          <Link
            to="/alerts"
            className="relative flex flex-none items-center gap-2 border border-divider bg-surface px-3 py-1.5 text-[12px] font-extrabold text-neutral-700 transition-colors duration-150 hover:bg-ink/[0.06]"
          >
            <Bell size={16} strokeWidth={2.2} />
            Notifications
            {openAlertsCount > 0 && (
              <span className="absolute -right-2 -top-2 flex size-4 items-center justify-center bg-accent text-[10px] font-extrabold text-ground">
                {openAlertsCount}
              </span>
            )}
          </Link>
        </div>

        <div className="mt-2 flex flex-wrap items-center justify-between gap-x-10 gap-y-6">
          <div className="flex items-stretch gap-5">
            <div className="flex w-28 flex-none items-center justify-center bg-accent sm:w-40">
              <Activity size={40} strokeWidth={2} className="text-ground sm:size-12" />
            </div>
            <div>
              <h1 className="max-w-[30ch] text-[clamp(24px,3.4vw,38px)] font-medium leading-[1.15] tracking-[-0.02em] text-ink">
                <span className="block">Your <span className="font-black text-accent">client relationships</span>,</span>
                <span className="block">BEFORE they <span className="font-black text-accent">become a problem</span>.</span>
              </h1>
              <p className="mt-3 max-w-[52ch] text-[15px] leading-relaxed text-neutral-700">
                These relationships have drifted away from their own normal pattern. Caught now, there is still time to act.
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-none sm:flex-row">
            <button className="btn btn-primary w-full justify-center px-6 py-3.5 text-base sm:w-auto" onClick={() => navigate("/alerts")}>
              Review the action queue
            </button>
            <Link className="btn btn-secondary w-full justify-center px-6 py-3.5 text-base sm:w-auto" to="/accounts">
              All accounts
            </Link>
          </div>
        </div>
      </section>

      <div className="flex flex-col gap-4 bg-ground px-6 pb-6 pt-2 sm:px-8 sm:pb-8">
        <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))]">
          <StatTile
            label="Healthy revenue"
            icon={Wallet}
            value={formatCurrency(healthyRevenueDisplay) + "/mo"}
            valueClassName="text-[clamp(26px,7.5vw,92px)] text-healthy-ink"
            className="bg-healthy-tint"
            style={{ animationDelay: "0ms" }}
          />
          <StatTile
            label="At-risk revenue"
            icon={TriangleAlert}
            value={formatCurrency(atRiskRevenueDisplay) + "/mo"}
            valueClassName="text-[clamp(26px,7.5vw,92px)] text-risk-ink"
            className="bg-risk-tint"
            style={{ animationDelay: "40ms" }}
            sub={
              <div className="mt-2.5 max-w-[260px]">
                <div className="h-[3px] w-full bg-divider/25">
                  <div
                    className="h-full origin-left bg-risk transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]"
                    style={{ transform: `scaleX(${barMounted ? atRiskShare : 0})` }}
                  />
                </div>
                <div className="mt-1 text-[11px] font-semibold text-neutral-600">
                  {Math.round(atRiskShare * 100)}% of monthly portfolio revenue
                </div>
              </div>
            }
          />
        </div>

        <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(140px,1fr))]">
          <StatTile
            label="Total accounts"
            icon={Users}
            value={Math.round(totalCountDisplay)}
            style={{ animationDelay: "80ms" }}
          />
          <TierCard tier="risk" label="At risk" accounts={atRisk} style={{ animationDelay: "120ms" }} />
          <TierCard tier="watch" label="Watch" accounts={watch} style={{ animationDelay: "160ms" }} />
          <TierCard tier="healthy" label="Healthy" accounts={healthy} style={{ animationDelay: "200ms" }} />
        </div>

        <div className="bg-surface p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-4 pb-4">
            <div>
              <h2 className="flex items-center gap-2.5 text-[27px] tracking-[-0.02em]">
                <ListChecks size={24} strokeWidth={2.2} className="text-neutral-600" />
                Accounts that need attention
              </h2>
              <p className="mt-1 text-[13px] text-neutral-700">Ranked by composite risk score.</p>
            </div>
            <Link className="btn btn-ghost" to="/accounts">
              See all {accounts.length} →
            </Link>
          </div>
          <AccountTable accounts={shortlist} compact />
        </div>

        <div className="bg-surface p-6">
          <h2 className="flex items-center gap-2.5 text-[19px]">
            <Activity size={20} strokeWidth={2.2} className="text-neutral-600" />
            Signals driving risk
          </h2>
          <p className="mt-1 text-[13px] text-neutral-700">
            For every tracked signal: how many open alerts cite it right now, and whether the underlying behavior is trending better or worse
            across the portfolio.
          </p>

          <div className="mt-5 flex flex-col">
            {signalHistoriesLoading ? (
              <Loading rows={5} />
            ) : (
              ALL_SIGNALS.map((signal) => {
              const count = signalCountMap.get(signal) ?? 0
              const trend = trendMap.get(signal)
              const direction = trend ? trendDirection(signal, trend.series) : "unknown"
              const DirectionIcon = direction === "worse" ? ArrowUp : direction === "better" ? ArrowDown : Minus
              const directionClass =
                direction === "worse" ? "text-risk-ink" : direction === "better" ? "text-healthy-ink" : "text-neutral-500"
              const directionLabel =
                direction === "worse" ? "Worsening" : direction === "better" ? "Improving" : direction === "flat" ? "Flat" : "—"
              return (
                <div key={signal} className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-divider py-3.5 last:border-b-0 sm:flex-nowrap">
                  <div className="w-full flex-none sm:w-[150px]">
                    <div className={cn("text-[13px] font-extrabold", count > 0 ? "text-neutral-800" : "text-neutral-500")}>
                      {SHORT_SIGNAL_LABEL[signal] ?? formatSignalName(signal)}
                    </div>
                    <div className="mt-1.5 h-1.5 w-full bg-divider/15">
                      <div
                        className={cn("h-full origin-left transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]", count > 0 ? "bg-risk" : "bg-transparent")}
                        style={{ transform: `scaleX(${barMounted ? count / maxSignalCount : 0})` }}
                      />
                    </div>
                    <div className={cn("mt-1 text-[11px] font-semibold tabular-nums", count > 0 ? "text-risk-ink" : "text-neutral-500")}>
                      {count} open alert{count === 1 ? "" : "s"}
                    </div>
                  </div>

                  <div className="h-10 min-w-0 flex-1">
                    {trend ? (
                      trend.series.length > 1 ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={trend.series}>
                            <YAxis hide domain={["dataMin", "dataMax"]} />
                            <Line
                              type="monotone"
                              dataKey="value"
                              stroke={direction === "worse" ? HEX.risk : direction === "better" ? HEX.healthy : HEX.ink}
                              strokeWidth={2}
                              dot={false}
                              isAnimationActive={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      ) : (
                        <span className="flex h-full items-center text-[11px] text-neutral-600">Not enough history yet</span>
                      )
                    ) : (
                      <span className="flex h-full items-center text-[11px] text-neutral-600">One-time signal — no trend line</span>
                    )}
                  </div>

                  <div className={cn("flex flex-none items-center gap-1 text-[11px] font-extrabold", directionClass)}>
                    {trend && <DirectionIcon size={13} strokeWidth={2.6} />}
                    {directionLabel}
                  </div>
                </div>
              )
              })
            )}
          </div>
        </div>

        <div className="bg-surface p-6">
          <h2 className="flex items-center gap-2.5 text-[19px]">
            <Bell size={20} strokeWidth={2.2} className="text-neutral-600" />
            Latest alerts
          </h2>

          <div className="mt-4 flex flex-col gap-3 border-t-2 border-divider pt-4">
            {alerts.slice(0, 5).map((alert, i) => {
              const history = signalHistories[alert.account_id] ?? []
              return (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  account={accountById.get(alert.account_id)}
                  latestSignals={history[history.length - 1]}
                  style={{ animationDelay: `${i * 30}ms` }}
                  updating={updatingId === alert.id}
                  justUpdated={justUpdatedId === alert.id}
                  onUpdateStatus={updateStatus}
                />
              )
            })}
            {alerts.length === 0 && <p className="py-6 text-center text-[13px] text-neutral-700">No alerts — everything's healthy.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
