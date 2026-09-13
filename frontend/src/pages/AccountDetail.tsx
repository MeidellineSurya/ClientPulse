import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { EmptyState } from "@/components/ui/EmptyState"
import { Loading } from "@/components/ui/Loading"
import { api, ApiError } from "@/lib/api"
import {
  computeDataCoverage,
  computeRevenueAtRisk,
  formatCurrency,
  formatDate,
  formatSignalName,
  formatSignalValue,
  MIN_DATA_COVERAGE_DAYS,
  riskTier,
  severityStyles,
  signalStatus,
  SIGNAL_STATUS_TEXT,
  TRACKED_SIGNALS,
} from "@/lib/format"
import { cn, HEX, nearestByDate, RISK_STYLES } from "@/lib/utils"
import type { AccountDetail as AccountDetailType, ContactChangeEvent, HealthScorePoint, SignalSnapshot } from "@/types/api"

const RISK_ALERT_THRESHOLD = 60 // mirrors backend/app/services/scoring_engine.py

function SignalSparkline({ signal, history }: { signal: keyof SignalSnapshot; history: SignalSnapshot[] }) {
  const data = history.map((row) => ({ period: row.period_start, value: row[signal] as number }))
  const allValues = data.map((d) => d.value)
  const latest = data[data.length - 1]
  const latestStatus = latest ? signalStatus(signal, latest.value, allValues) : null
  const statusLabel = latestStatus === "bad" ? "Risk" : latestStatus === "watch" ? "Watch" : "Good"
  const statusDotClass = latestStatus === "bad" ? "bg-risk" : latestStatus === "watch" ? "bg-watch" : "bg-healthy"

  return (
    <div className="border border-divider p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="kicker">{formatSignalName(signal)}</div>
        {latestStatus && (
          <span className={cn("flex items-center gap-1.5 text-[10.5px] font-extrabold uppercase tracking-[0.05em]", SIGNAL_STATUS_TEXT[latestStatus])}>
            <span className={cn("size-1.5 flex-none", statusDotClass)} aria-hidden="true" />
            {statusLabel}
          </span>
        )}
      </div>
      <div className="mt-2 h-28 w-full">
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -12 }}>
              <XAxis
                dataKey="period"
                tickFormatter={formatDate}
                tick={{ fontSize: 10, fill: "#7d7979" }}
                axisLine={false}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={["dataMin - 1", "dataMax + 1"]}
                tickFormatter={(v: number) => formatSignalValue(signal, v)}
                tick={{ fontSize: 10, fill: "#7d7979" }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip
                contentStyle={{ border: "1px solid rgba(32,30,29,0.4)", borderRadius: 0, background: "#f3f2f2", fontSize: 12 }}
                labelFormatter={(label) => (typeof label === "string" ? formatDate(label) : String(label ?? ""))}
                formatter={(value) => [formatSignalValue(signal, value as number), formatSignalName(signal)]}
              />
              <Line
                type="linear"
                dataKey="value"
                stroke={HEX.ink}
                strokeWidth={2}
                dot={(props) => {
                  const status = signalStatus(signal, props.value as number, allValues)
                  const fill = status === "bad" ? HEX.risk : status === "watch" ? HEX.watch : HEX.healthy
                  return <circle key={props.index} cx={props.cx} cy={props.cy} r={3} fill={fill} stroke="none" />
                }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="flex h-full items-center text-[12px] text-neutral-600">No signal history yet</p>
        )}
      </div>
    </div>
  )
}

function ContactChangeChart({
  events,
  history,
}: {
  events: ContactChangeEvent[]
  history: SignalSnapshot[]
}) {
  const eventByDate = new Map(events.map((event) => [event.period_end, event]))
  const denominator = Math.max(1, history.length - 1)
  const points = history.map((row, index) => ({
    x: 4 + (index / denominator) * 92,
    y: eventByDate.has(row.period_end) ? 10 : 38,
    event: eventByDate.get(row.period_end),
  }))
  const summary = events.length === 0
    ? `No changes across ${history.length} reporting periods`
    : `${events.length} ${events.length === 1 ? "change" : "changes"} across ${history.length} reporting periods`

  return (
    <div className="border border-divider bg-surface p-4 [grid-column:1/-1]">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[15px] font-extrabold">Contact changes</h3>
        <span className="text-[11px] tabular-nums text-neutral-600">{summary}</span>
      </div>
      <svg
        aria-label="Contact change events over time"
        className="mt-3 h-24 w-full overflow-visible"
        role="img"
        viewBox="0 0 100 48"
        preserveAspectRatio="none"
      >
        <line x1="4" y1="38" x2="96" y2="38" stroke={HEX.ink} strokeOpacity="0.18" strokeWidth="0.8" />
        {points.length > 1 && (
          <polyline
            points={points.map((point) => `${point.x},${point.y}`).join(" ")}
            fill="none"
            stroke={events.length > 0 ? HEX.accent : HEX.ink}
            strokeWidth="1.4"
            vectorEffect="non-scaling-stroke"
          />
        )}
        {points.filter((point) => point.event).map((point) => (
          <line
            key={point.event!.period_end}
            data-testid="contact-event-marker"
            x1={point.x}
            x2={point.x}
            y1="6"
            y2="14"
            stroke={HEX.accent}
            strokeWidth="3"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      {events.length > 0 ? (
        <ol className="mt-2 grid gap-3 border-t border-divider pt-3 md:grid-cols-3">
          {events.map((event) => (
            <li key={event.period_end} className="min-w-0 text-[11.5px] leading-relaxed text-neutral-700">
              <span className="block font-extrabold text-ink">{formatDate(event.period_end)}</span>
              <span className="block break-words">
                {event.previous_contact_email} → {event.current_contact_email}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 border-t border-divider pt-2 text-[11.5px] text-neutral-600">
          The recorded contact identity stayed consistent throughout this history.
        </p>
      )}
    </div>
  )
}

export function AccountDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [account, setAccount] = useState<AccountDetailType | null>(null)
  const [healthHistory, setHealthHistory] = useState<HealthScorePoint[]>([])
  const [error, setError] = useState<string | null>(null)
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  useEffect(() => {
    if (!id) return
    setAccount(null)
    setHoveredIdx(null)
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

  const coverage = computeDataCoverage(account.signal_history)
  const tier = riskTier(account.composite_score)
  const style = RISK_STYLES[tier]
  const revenueAtRisk = computeRevenueAtRisk(account.contract_value_monthly, account.composite_score)
  const latestAlertWithBrief = account.alerts.find((a) => a.ai_brief)
  const scoreHistoryData = healthHistory.map((p) => ({ date: p.computed_at, score: p.composite_score }))
  const statusLabel = tier === "risk" ? "At risk" : tier === "watch" ? "Watch" : tier === "unscored" ? "Unscored" : "Healthy"
  const activePoint = healthHistory[hoveredIdx ?? healthHistory.length - 1] ?? null
  const activeSnapshot = activePoint
    ? nearestByDate(account.signal_history, activePoint.computed_at, (row) => row.period_start)
    : null
  const activeTier = activePoint ? riskTier(activePoint.composite_score) : tier

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
          <div className="min-w-0 flex-1 sm:min-w-[280px]">
            <h1 className="break-words text-[clamp(28px,6vw,40px)] tracking-[-0.035em]">{account.name}</h1>
            <div className="mt-1 text-[13.5px] text-neutral-700">
              Client since {formatDate(account.contract_start_date)} · {account.primary_contact_email ?? "no contact on file"}
            </div>
            {account.contact_changed_at && (
              <div className="mt-2.5 inline-block bg-accent-100 px-3.5 py-1.5 text-[12.5px]">
                <span className="font-extrabold uppercase tracking-[0.05em] text-accent-700">New point of contact</span>{" "}
                as of {formatDate(account.contact_changed_at)}: {account.primary_contact_email}
                {account.previous_contact_email && <> (was {account.previous_contact_email})</>}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-stretch gap-y-5">
            {coverage.isSufficient ? (
              <>
                <div className={cn("min-w-0 border-l-[3px] pl-4 pr-7", style.borderLeft)}>
                  <div className="kicker">Risk score</div>
                  <div className={cn("break-words text-[clamp(40px,8vw,68px)] font-extrabold leading-[0.92] tracking-[-0.05em] tabular-nums", style.text)}>
                    {account.composite_score !== null ? account.composite_score.toFixed(0) : "—"}
                  </div>
                  <div className={cn("text-[12.5px] font-extrabold uppercase tracking-[0.06em]", style.text)}>{statusLabel}</div>
                </div>

                <div className="min-w-0 border-l border-divider pl-7">
                  <div className="kicker">Revenue at risk</div>
                  <div className="mt-1 break-words text-[clamp(24px,6vw,38px)] font-extrabold leading-tight tracking-[-0.04em] tabular-nums">
                    {formatCurrency(revenueAtRisk)}
                  </div>
                  <div className="text-[13px] text-neutral-800">{formatCurrency(account.contract_value_monthly)}/mo contract</div>
                  <div className="mt-1.5 text-[12px] text-neutral-700">
                    {account.health_computed_at ? "Last scored " + formatDate(account.health_computed_at) : "Never scored"}
                  </div>
                </div>
              </>
            ) : (
              <div className="min-w-0 border-l-[3px] border-l-neutral-400 pl-4">
                <div className="kicker">Risk score</div>
                <div className="text-[22px] font-extrabold leading-tight text-neutral-600">Collecting data</div>
                <div className="mt-1 text-[12px] text-neutral-700">
                  {coverage.days} of {MIN_DATA_COVERAGE_DAYS} days collected
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {coverage.isSufficient ? (
        <>
          <section className="rule px-10 pb-7 pt-6">
            <h2 className="text-[17px]">Composite risk, over time</h2>
            <p className="mb-3.5 text-[12.5px] text-neutral-700">
              Dashed line is the alert threshold ({RISK_ALERT_THRESHOLD}). Hover the line to see what was happening in that period.
            </p>
            <div className="h-[230px] w-full border border-divider bg-surface">
              {scoreHistoryData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={scoreHistoryData}
                    margin={{ top: 16, right: 16, bottom: 8, left: -16 }}
                    onMouseMove={(state) => {
                      if (typeof state.activeTooltipIndex === "number") setHoveredIdx(state.activeTooltipIndex)
                    }}
                    onMouseLeave={() => setHoveredIdx(null)}
                  >
                    <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fontSize: 11, fill: "#7d7979" }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#7d7979" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ border: "1px solid rgba(32,30,29,0.4)", borderRadius: 0, background: "#f3f2f2", fontSize: 12 }}
                      labelFormatter={(label) => (typeof label === "string" ? formatDate(label) : String(label ?? ""))}
                      formatter={(v) => [v, "Risk"]}
                    />
                    <ReferenceLine y={RISK_ALERT_THRESHOLD} stroke={HEX.accent} strokeDasharray="7 6" />
                    <Line
                      type="linear"
                      dataKey="score"
                      stroke={HEX[tier]}
                      strokeWidth={3}
                      dot={{ r: 1.8, fill: HEX[tier], strokeWidth: 0 }}
                      activeDot={{ r: 4.5, fill: HEX.accent, strokeWidth: 0 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="flex h-full items-center justify-center text-[13px] text-neutral-700">
                  No score history yet — run /score/recompute for this account.
                </p>
              )}
            </div>

            {activePoint && (
              <div className="mt-3 flex flex-wrap items-center gap-x-8 gap-y-3 border border-divider bg-surface px-5 py-3.5">
                <div className="flex-none">
                  <div className="kicker">{formatDate(activePoint.computed_at)}</div>
                  <div className={cn("text-[22px] font-extrabold leading-none tabular-nums", RISK_STYLES[activeTier].text)}>
                    {activePoint.composite_score.toFixed(0)}
                  </div>
                </div>
                <div className="h-8 w-px flex-none bg-divider" aria-hidden="true" />
                {activeSnapshot ? (
                  <div className="flex flex-1 flex-wrap gap-x-6 gap-y-2">
                    {TRACKED_SIGNALS.map((signal) => (
                      <div key={signal} className="flex-none">
                        <div className="text-[10px] uppercase tracking-[0.08em] text-neutral-600">{formatSignalName(signal)}</div>
                        <div className="text-[14px] font-extrabold tabular-nums">
                          {formatSignalValue(signal, activeSnapshot[signal] as number)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[12.5px] text-neutral-700">No signal detail recorded for this period.</p>
                )}
              </div>
            )}
          </section>

          <section className="px-10 pb-3 pt-6">
            <h2 className="text-[17px]">Signal trends</h2>
            <p className="mt-1 text-[12.5px] text-neutral-700">
              Raw signal values over each scored period. Good/Watch/Risk is colour-coded against this account's own history, not a fixed
              threshold — the same "compare to its own baseline" rule the risk score itself uses.
            </p>
          </section>
          <section className="grid gap-4 px-10 pb-8 [grid-template-columns:repeat(auto-fit,minmax(280px,1fr))]">
            <ContactChangeChart events={account.contact_events ?? []} history={account.signal_history} />
            {TRACKED_SIGNALS.map((signal) => (
              <SignalSparkline key={signal} signal={signal} history={account.signal_history} />
            ))}
          </section>

          {latestAlertWithBrief && (
            <section className="rule bg-surface px-10 pb-7 pt-6">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-[10.5px] font-extrabold uppercase tracking-[0.1em] text-accent-700">AI brief</div>
                <span className={cn("px-2 py-[3px] text-[10.5px] font-extrabold uppercase tracking-[0.05em]", severityStyles[latestAlertWithBrief.severity])}>
                  {latestAlertWithBrief.severity}
                </span>
              </div>

              {latestAlertWithBrief.signals_fired.length > 0 && (
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] font-extrabold uppercase tracking-[0.08em] text-neutral-600">Signals detected</span>
                  {latestAlertWithBrief.signals_fired.map((signal) => (
                    <span key={signal} className="border border-divider bg-ground px-2 py-[3px] text-[10.5px] font-extrabold uppercase tracking-[0.05em] text-neutral-800">
                      {formatSignalName(signal)}
                    </span>
                  ))}
                </div>
              )}

              <p className="mb-4 mt-3 whitespace-pre-line text-[15px] leading-relaxed">{latestAlertWithBrief.ai_brief}</p>

              {latestAlertWithBrief.suggested_action && (
                <div className="bg-neutral-700 px-4 py-2.5">
                  <div className="text-[10.5px] font-extrabold uppercase tracking-[0.06em] text-neutral-300">Recommended action</div>
                  <div className="mt-1 text-[17px] font-extrabold leading-tight text-ground">{latestAlertWithBrief.suggested_action}</div>
                </div>
              )}

              <div className="mt-4 border-t border-divider pt-2.5 text-[11px] text-neutral-600">
                Written from the signals above. The score itself is deterministic — the model never sets it.
              </div>
            </section>
          )}
        </>
      ) : (
        <section className="rule px-10 py-10">
          <EmptyState
            title={
              coverage.daysRemaining <= 21 ? "Analysis will be available soon." : "This client needs more data before analysis is available."
            }
            body={`ClientPulse requires at least ${MIN_DATA_COVERAGE_DAYS} days of activity to identify meaningful trends and calculate a reliable risk score.`}
            extra={
              <div className="mt-4 text-[12.5px] font-semibold text-neutral-600">
                {coverage.days} of {MIN_DATA_COVERAGE_DAYS} days collected
                {coverage.daysRemaining > 0 && ` · ${coverage.daysRemaining} day${coverage.daysRemaining === 1 ? "" : "s"} to go`}
              </div>
            }
          />
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
