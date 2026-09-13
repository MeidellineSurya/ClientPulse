import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import { EmptyState } from "@/components/ui/EmptyState"
import { Loading } from "@/components/ui/Loading"
import { Segmented } from "@/components/ui/Segmented"
import { api, ApiError } from "@/lib/api"
import { formatDate, formatSignalName, severityStyles } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { Alert } from "@/types/api"

const STATUS_FLOW: Record<Alert["status"], Alert["status"]> = {
  open: "acknowledged",
  acknowledged: "resolved",
  resolved: "resolved",
}

const STATUS_LABEL: Record<Alert["status"], string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
}

const FILTERS = ["All", "Open", "Acknowledged", "Resolved"] as const
type Filter = (typeof FILTERS)[number]

export function Alerts() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>("All")

  useEffect(() => {
    api
      .listAlerts()
      .then(setAlerts)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load alerts"))
  }, [])

  async function advanceStatus(alert: Alert) {
    const nextStatus = STATUS_FLOW[alert.status]
    if (nextStatus === alert.status) return
    setUpdatingId(alert.id)
    try {
      const updated = await api.setAlertStatus(alert.id, nextStatus)
      setAlerts((prev) => prev?.map((a) => (a.id === alert.id ? updated : a)) ?? null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update alert")
    } finally {
      setUpdatingId(null)
    }
  }

  const shown = useMemo(() => {
    if (!alerts) return []
    if (filter === "All") return alerts
    return alerts.filter((a) => STATUS_LABEL[a.status] === filter)
  }, [alerts, filter])

  const openCount = alerts?.filter((a) => a.status === "open").length ?? 0

  return (
    <div>
      <header className="rule px-10 pb-6 pt-8">
        <h1 className="max-w-[20ch] text-[34px] tracking-[-0.03em]">Catch problems while there's still time.</h1>
        <p className="mt-2 max-w-[66ch] text-[13.5px] text-neutral-700">
          An alert fires only when composite risk crosses the threshold <em>and</em> the trend has worsened for three
          periods running — so this queue stays short enough to work through each morning.
        </p>
      </header>

      {error && <div className="border-b border-divider bg-risk-tint px-10 py-3 text-[13px] text-risk-ink">{error}</div>}

      <div className="flex flex-wrap items-center gap-3 border-b border-divider px-10 py-3.5">
        <Segmented name="alert-filter" options={FILTERS} value={filter} onChange={setFilter} />
        <div className="ml-auto text-[12.5px] text-neutral-700">
          {shown.length} alerts · {openCount} open
        </div>
      </div>

      <div className="flex flex-col gap-4 px-10 pb-12 pt-5">
        {!alerts && <Loading rows={4} />}
        {alerts && shown.length === 0 && <EmptyState title="Queue clear" body="Nothing in this filter needs your attention right now." />}
        {shown.map((alert) => (
          <article key={alert.id} className="border border-divider">
            <div className="flex flex-wrap items-start gap-4 border-b border-divider px-5 py-4">
              <div>
                <div className="flex items-center gap-2.5">
                  <Link to={`/accounts/${alert.account_id}`} className="text-[18px] font-extrabold tracking-[-0.02em] hover:text-accent-700">
                    {alert.account_name ?? alert.account_id}
                  </Link>
                  <span className={cn("px-2 py-[3px] text-[10.5px] font-extrabold uppercase tracking-[0.05em]", severityStyles[alert.severity])}>
                    {alert.severity}
                  </span>
                  <span className="border border-divider px-2 py-[3px] text-[10.5px] font-extrabold uppercase tracking-[0.05em] text-neutral-700">
                    {STATUS_LABEL[alert.status]}
                  </span>
                </div>
                <div className="mt-0.5 text-[12px] text-neutral-700">
                  Triggered {formatDate(alert.triggered_at)} · {alert.signals_fired.map(formatSignalName).join(", ") || "no signals recorded"}
                </div>
              </div>
              {alert.status !== "resolved" && (
                <button
                  className="btn btn-secondary ml-auto"
                  disabled={updatingId === alert.id}
                  onClick={() => advanceStatus(alert)}
                >
                  Mark {STATUS_LABEL[STATUS_FLOW[alert.status]]}
                </button>
              )}
            </div>
            {alert.ai_brief && (
              <div className="px-5 py-4 text-[14px] leading-relaxed">
                <p className="whitespace-pre-line">{alert.ai_brief}</p>
                {alert.suggested_action && (
                  <div className="mt-3 border-l-[3px] border-ink pl-3.5">
                    <div className="kicker">Recommended</div>
                    <div className="text-[15px] font-extrabold leading-snug">{alert.suggested_action}</div>
                  </div>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}
