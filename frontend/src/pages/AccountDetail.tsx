import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { Loading } from "@/components/ui/Loading"
import { api, ApiError } from "@/lib/api"
import { computeRevenueAtRisk, formatCurrency, formatDate, formatSignalName, riskTier, severityStyles } from "@/lib/format"
import { cn, HEX, RISK_STYLES } from "@/lib/utils"
import type { AccountDetail as AccountDetailType, HealthScorePoint, SignalSnapshot } from "@/types/api"

const RISK_ALERT_THRESHOLD = 60 // mirrors backend/app/services/scoring_engine.py

const TRACKED_SIGNALS: Array<keyof SignalSnapshot> = [
  "avg_response_time_hours",
  "meetings_cancelled",
  "invoice_days_late",
  "meetings_scheduled",
]

function SignalSparkline({ signal, history }: { signal: keyof SignalSnapshot; history: SignalSnapshot[] }) {
  const data = history.map((row) => ({ period: row.period_start, value: row[signal] as number }))
  return (
    <div className="border border-divider p-4">
      <div className="kicker">{formatSignalName(signal)}</div>
      <div className="mt-1 h-20 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 4, bottom: 2, left: 4 }}>
            <YAxis hide domain={["dataMin - 1", "dataMax + 1"]} />
            <Tooltip
              contentStyle={{ border: "1px solid rgba(32,30,29,0.4)", borderRadius: 0, background: "#f3f2f2", fontSize: 12 }}
              labelFormatter={(label) => (typeof label === "string" ? formatDate(label) : String(label ?? ""))}
              formatter={(value) => [String(value), formatSignalName(signal)]}
            />
            <Line type="monotone" dataKey="value" stroke={HEX.ink} strokeWidth={1.7} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function AccountDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [account, setAccount] = useState<AccountDetailType | null>(null)
  const [healthHistory, setHealthHistory] = useState<HealthScorePoint[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setAccount(null)
    api
      .getAccount(id)
      .then(setAccount)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load account"))
    api
      .getAccountHealthHistory(id)
      .then(setHealthHistory)
      .catch(() => {
        // Non-fatal: the risk-over-time chart just renders empty if this fails.
      })
  }, [id])

  if (error) {
    return <div className="m-10 border border-risk px-4 py-3 text-[13px] text-risk-ink">Couldn't load account: {error}</div>
  }

  if (!account) {
    return (
      <div className="p-10">
        <Loading rows={6} />
      </div>
    )
  }

  const tier = riskTier(account.composite_score)
  const style = RISK_STYLES[tier]
  const revenueAtRisk = computeRevenueAtRisk(account.contract_value_monthly, account.composite_score)
  const latestAlertWithBrief = account.alerts.find((a) => a.ai_brief)
  const scoreHistoryData = healthHistory.map((p) => ({ date: p.computed_at, score: p.composite_score }))
  const statusLabel = tier === "risk" ? "At risk" : tier === "watch" ? "Watch" : tier === "unscored" ? "Unscored" : "Healthy"

  return (
    <div>
      <div className="flex items-center gap-2.5 border-b border-divider px-10 py-3">
        <button className="btn btn-ghost" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <span className="text-[12px] text-neutral-600">Accounts / {account.name}</span>
      </div>

      <header className="rule px-10 pb-7 pt-8">
        <div className="flex flex-wrap items-start gap-10">
          <div className="min-w-[280px] flex-1">
            <h1 className="text-[40px] tracking-[-0.035em]">{account.name}</h1>
            <div className="mt-1 text-[13.5px] text-neutral-700">
              client since {formatDate(account.contract_start_date)} · {account.primary_contact_email ?? "no contact on file"}
            </div>
          </div>

          <div className="flex items-stretch">
            <div className={cn("border-l-4 pl-4 pr-7", style.borderLeft)}>
              <div className="kicker">Risk score</div>
              <div className={cn("text-[68px] font-extrabold leading-[0.92] tracking-[-0.05em]", style.text)}>
                {account.composite_score !== null ? account.composite_score.toFixed(0) : "—"}
              </div>
              <div className={cn("text-[12.5px] font-extrabold uppercase tracking-[0.06em]", style.text)}>{statusLabel}</div>
            </div>

            <div className="border-l border-divider pl-7">
              <div className="kicker">Revenue at risk</div>
              <div className="mt-1 text-[38px] font-extrabold leading-tight tracking-[-0.04em]">{formatCurrency(revenueAtRisk)}</div>
              <div className="text-[13px] text-neutral-800">{formatCurrency(account.contract_value_monthly)}/mo contract</div>
              <div className="mt-1.5 text-[12px] text-neutral-700">
                {account.health_computed_at ? "Last scored " + formatDate(account.health_computed_at) : "Never scored"}
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="rule px-10 pb-7 pt-6">
        <h2 className="text-[17px]">Composite risk, over time</h2>
        <p className="mb-3.5 text-[12.5px] text-neutral-700">Dashed line is the alert threshold ({RISK_ALERT_THRESHOLD}).</p>
        <div className="h-[230px] w-full border border-divider bg-surface">
          {scoreHistoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={scoreHistoryData} margin={{ top: 16, right: 16, bottom: 8, left: -16 }}>
                <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fontSize: 11, fill: "#7d7979" }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#7d7979" }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ border: "1px solid rgba(32,30,29,0.4)", borderRadius: 0, background: "#f3f2f2", fontSize: 12 }}
                  labelFormatter={(label) => (typeof label === "string" ? formatDate(label) : String(label ?? ""))}
                  formatter={(v) => [v, "Risk"]}
                />
                <ReferenceLine y={RISK_ALERT_THRESHOLD} stroke={HEX.accent} strokeDasharray="7 6" />
                <Line type="monotone" dataKey="score" stroke={HEX[tier]} strokeWidth={2.4} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="flex h-full items-center justify-center text-[13px] text-neutral-700">
              No score history yet — run /score/recompute for this account.
            </p>
          )}
        </div>
      </section>

      <section className="px-10 pb-3 pt-6">
        <h2 className="text-[17px]">Signal trends</h2>
        <p className="mt-1 text-[12.5px] text-neutral-700">Raw signal values over each scored period.</p>
      </section>
      <section className="grid gap-4 px-10 pb-8 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
        {TRACKED_SIGNALS.map((signal) => (
          <SignalSparkline key={signal} signal={signal} history={account.signal_history} />
        ))}
      </section>

      {latestAlertWithBrief && (
        <section className="rule bg-surface px-10 pb-7 pt-6">
          <div className="flex items-center gap-2">
            <div className="text-[10.5px] font-extrabold uppercase tracking-[0.1em] text-accent-700">AI brief</div>
            <span className={cn("px-2 py-[3px] text-[10.5px] font-extrabold uppercase tracking-[0.05em]", severityStyles[latestAlertWithBrief.severity])}>
              {latestAlertWithBrief.severity}
            </span>
          </div>
          <p className="mb-4 mt-2 whitespace-pre-line text-[15px] leading-relaxed">{latestAlertWithBrief.ai_brief}</p>
          {latestAlertWithBrief.suggested_action && (
            <div className="border-t-2 border-divider pt-3.5">
              <div className="kicker">Recommended action</div>
              <div className="my-1.5 text-[19px] font-extrabold leading-tight">{latestAlertWithBrief.suggested_action}</div>
            </div>
          )}
          <div className="mt-4 border-t border-divider pt-2.5 text-[11px] text-neutral-600">
            Written from the signals above. The score itself is deterministic — the model never sets it.
          </div>
        </section>
      )}

      <section className="px-10 pb-12 pt-7">
        <h2 className="mb-2.5 text-[17px]">Alerts for this account</h2>
        {account.alerts.length === 0 ? (
          <p className="text-[13px] text-neutral-700">No alerts have fired for this account.</p>
        ) : (
          <div className="border-t-2 border-divider">
            {account.alerts.map((alert) => (
              <Link
                key={alert.id}
                to="/alerts"
                className="flex flex-wrap items-center gap-3 border-b border-divider py-3 text-left hover:bg-ink/[0.05]"
              >
                <span className={cn("px-2 py-[3px] text-[10.5px] font-extrabold uppercase tracking-[0.05em]", severityStyles[alert.severity])}>
                  {alert.severity}
                </span>
                <span className="text-[13px]">{alert.signals_fired.map(formatSignalName).join(", ") || "No signals recorded"}</span>
                <span className="ml-auto whitespace-nowrap text-[11px] text-neutral-600">{formatDate(alert.triggered_at)} · {alert.status}</span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
