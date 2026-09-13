import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { AccountTable } from "@/components/AccountTable"
import { Loading } from "@/components/ui/Loading"
import { StatTile } from "@/components/ui/StatTile"
import { api, ApiError } from "@/lib/api"
import { computeRevenueAtRisk, formatCurrency, formatDate, formatSignalName, riskTier } from "@/lib/format"
import { HEX } from "@/lib/utils"
import type { Alert, AccountSummary } from "@/types/api"

export function Portfolio() {
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState<AccountSummary[] | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listAccounts()
      .then(setAccounts)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load accounts"))
    api.listAlerts().then(setAlerts).catch(() => {
      // Non-fatal: the "latest alerts" panel just renders empty if this fails.
    })
  }, [])

  const atRisk = useMemo(() => accounts?.filter((a) => riskTier(a.composite_score) === "risk") ?? [], [accounts])
  const watch = useMemo(() => accounts?.filter((a) => riskTier(a.composite_score) === "watch") ?? [], [accounts])
  const healthy = useMemo(() => accounts?.filter((a) => riskTier(a.composite_score) === "healthy") ?? [], [accounts])

  const revenueAtRisk = useMemo(
    () => atRisk.reduce((sum, a) => sum + computeRevenueAtRisk(a.contract_value_monthly, a.composite_score), 0),
    [atRisk],
  )
  const healthyRevenue = useMemo(() => healthy.reduce((sum, a) => sum + a.contract_value_monthly, 0), [healthy])
  const shortlist = useMemo(
    () => [...(accounts ?? [])].sort((a, b) => (b.composite_score ?? -1) - (a.composite_score ?? -1)).slice(0, 5),
    [accounts],
  )

  if (error) {
    return <div className="m-10 border border-risk px-4 py-3 text-[13px] text-risk-ink">Couldn't load accounts: {error}</div>
  }

  if (!accounts) {
    return (
      <div className="p-10">
        <Loading rows={8} />
      </div>
    )
  }

  return (
    <div>
      <section className="rule px-10 pb-9 pt-11">
        <h1 className="mt-2.5 max-w-[20ch] text-[clamp(30px,3.6vw,44px)] leading-[1.04] tracking-[-0.035em]">
          Your client relationships, before they become a problem.
        </h1>

        <div className="mt-8 grid items-end gap-8 [grid-template-columns:repeat(auto-fit,minmax(340px,1fr))]">
          <div>
            <div className="text-[clamp(52px,8.5vw,104px)] font-extrabold leading-[0.86] tracking-[-0.05em] text-accent-700">
              {formatCurrency(revenueAtRisk)}
            </div>
            <div className="mt-3.5 text-[17px] font-semibold">annualised revenue currently at risk</div>
            <div className="mt-2.5 text-[13px] text-neutral-800">{atRisk.length} accounts crossing the composite risk threshold</div>
          </div>
          <div className="border-l-2 border-divider pl-7">
            <p className="mb-4 max-w-[44ch] text-[15px] leading-relaxed">
              These relationships have drifted away from their own normal pattern. Caught now, there is still time to act.
            </p>
            <div className="flex gap-2.5">
              <button className="btn btn-primary" onClick={() => navigate("/alerts")}>
                Review the action queue
              </button>
              <Link className="btn btn-secondary" to="/accounts">
                All accounts
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="rule grid [grid-template-columns:repeat(auto-fit,minmax(190px,1fr))]">
        <StatTile label="Total accounts" value={accounts.length} />
        <StatTile label="Accounts at risk" value={atRisk.length} accent={atRisk.length > 0} />
        <StatTile label="Watch" value={watch.length} />
        <StatTile label="Healthy revenue" value={formatCurrency(healthyRevenue) + "/mo"} />
      </section>

      <section className="flex items-baseline justify-between gap-4 px-10 pb-2.5 pt-8">
        <div>
          <h2 className="text-[24px] tracking-[-0.02em]">Accounts that need attention</h2>
          <p className="mt-1 text-[13px] text-neutral-700">Ranked by composite risk score.</p>
        </div>
        <Link className="btn btn-ghost" to="/accounts">
          See all {accounts.length} →
        </Link>
      </section>
      <section className="px-10 pb-8">
        <AccountTable accounts={shortlist} compact />
      </section>

      <section className="border-t-2 border-divider px-10 pb-12 pt-7">
        <h2 className="mb-3 text-[17px]">Latest alerts</h2>
        <div className="border-t-2 border-divider">
          {alerts.slice(0, 5).map((alert) => {
            return (
              <button
                key={alert.id}
                onClick={() => navigate(`/accounts/${alert.account_id}`)}
                className="flex w-full items-start gap-3 border-b border-divider py-2.5 text-left hover:bg-ink/[0.05]"
              >
                <span className="mt-1.5 h-2 w-2 flex-none" style={{ background: HEX[alert.severity === "critical" || alert.severity === "high" ? "risk" : alert.severity === "medium" ? "watch" : "healthy"] }} />
                <div className="min-w-0">
                  <div className="text-[13.5px] font-extrabold">{alert.account_name ?? alert.account_id}</div>
                  <div className="text-[12px] leading-snug text-neutral-700">{alert.signals_fired.map(formatSignalName).join(" · ")}</div>
                </div>
                <span className="ml-auto whitespace-nowrap text-[11px] text-neutral-600">{formatDate(alert.triggered_at)}</span>
              </button>
            )
          })}
          {alerts.length === 0 && <p className="py-6 text-center text-[13px] text-neutral-700">No alerts — everything's healthy.</p>}
        </div>
      </section>
    </div>
  )
}
