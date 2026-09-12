import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api, ApiError } from "@/lib/api"
import {
  computeRevenueAtRisk,
  formatCurrency,
  formatDate,
  formatSignalName,
  healthTier,
  healthTierStyles,
  severityStyles,
} from "@/lib/format"
import type { AccountDetail as AccountDetailType, HealthScorePoint, SignalSnapshot } from "@/types/api"

const TRACKED_SIGNALS: Array<keyof SignalSnapshot> = [
  "avg_response_time_hours",
  "meetings_cancelled",
  "invoice_days_late",
  "meetings_scheduled",
]

function SignalSparkline({ signal, history }: { signal: keyof SignalSnapshot; history: SignalSnapshot[] }) {
  const data = history.map((row) => ({ period: row.period_start, value: row[signal] as number }))
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{formatSignalName(signal)}</CardTitle>
      </CardHeader>
      <CardContent className="h-24 pt-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="period" hide />
            <YAxis hide domain={["auto", "auto"]} />
            <Tooltip
              labelFormatter={(label) => (typeof label === "string" ? formatDate(label) : String(label ?? ""))}
              formatter={(value) => [String(value), formatSignalName(signal)]}
            />
            <Line type="monotone" dataKey="value" stroke="var(--color-primary)" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function AccountDetail() {
  const { id } = useParams<{ id: string }>()
  const [account, setAccount] = useState<AccountDetailType | null>(null)
  const [healthHistory, setHealthHistory] = useState<HealthScorePoint[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api
      .getAccount(id)
      .then(setAccount)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load account"))
    api
      .getAccountHealthHistory(id)
      .then(setHealthHistory)
      .catch(() => {
        // Non-fatal: the score-over-time chart just renders empty if this fails.
      })
  }, [id])

  if (error) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        Couldn't load account: {error}
      </div>
    )
  }

  if (!account) {
    return <p className="text-muted-foreground">Loading…</p>
  }

  const tier = healthTier(account.composite_score)
  const revenueAtRisk = computeRevenueAtRisk(account.contract_value_monthly, account.composite_score)
  const latestAlertWithBrief = account.alerts.find((a) => a.ai_brief)
  const scoreHistoryData = healthHistory.map((p) => ({ date: p.computed_at, score: p.composite_score }))

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/" className="text-sm text-muted-foreground hover:underline">
          ← Portfolio
        </Link>
        <div className="mt-1 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{account.name}</h1>
            <p className="text-sm text-muted-foreground">
              {formatCurrency(account.contract_value_monthly)}/mo · {account.primary_contact_email ?? "no contact on file"}
            </p>
          </div>
          <Badge variant="secondary" className={`text-base ${healthTierStyles[tier]}`}>
            {account.composite_score !== null ? account.composite_score.toFixed(0) : "Unscored"}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Revenue at risk</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold text-red-600">{formatCurrency(revenueAtRisk)}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Last scored</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {account.health_computed_at ? formatDate(account.health_computed_at) : "Never"}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Composite risk score over time</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          {scoreHistoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={scoreHistoryData}>
                <XAxis dataKey="date" tickFormatter={formatDate} />
                <YAxis domain={[0, 100]} />
                <Tooltip
                  labelFormatter={(label) => (typeof label === "string" ? formatDate(label) : String(label ?? ""))}
                />
                <Line type="monotone" dataKey="score" stroke="var(--color-destructive)" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
              No score history yet — run /score/recompute for this account.
            </p>
          )}
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-3 text-lg font-medium">Signal trends</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {TRACKED_SIGNALS.map((signal) => (
            <SignalSparkline key={signal} signal={signal} history={account.signal_history} />
          ))}
        </div>
      </div>

      {latestAlertWithBrief && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              AI brief
              <Badge variant="secondary" className={severityStyles[latestAlertWithBrief.severity]}>
                {latestAlertWithBrief.severity}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm whitespace-pre-line">{latestAlertWithBrief.ai_brief}</p>
            {latestAlertWithBrief.suggested_action && (
              <p className="text-sm font-medium">Suggested action: {latestAlertWithBrief.suggested_action}</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
