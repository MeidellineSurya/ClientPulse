import { useEffect, useMemo, useState } from "react"

import { AlertCard } from "@/components/AlertCard"
import { EmptyState } from "@/components/ui/EmptyState"
import { Loading } from "@/components/ui/Loading"
import { Segmented } from "@/components/ui/Segmented"
import { api, ApiError } from "@/lib/api"
import { computeDataCoverage } from "@/lib/format"
import { useSignalHistories } from "@/lib/useSignalHistories"
import type { Alert, AccountSummary } from "@/types/api"

const STATUS_LABEL: Record<Alert["status"], string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
}

const FILTERS = ["All", "Open", "Acknowledged", "Resolved"] as const
type Filter = (typeof FILTERS)[number]

export function Alerts() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null)
  const [accounts, setAccounts] = useState<AccountSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const [justUpdatedId, setJustUpdatedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>("All")

  useEffect(() => {
    api
      .listAlerts()
      .then(setAlerts)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load alerts"))
    api.listAccounts().then(setAccounts).catch(() => {
      // Non-fatal: cards just omit the risk-score/stats readout if this fails.
    })
  }, [])

  const accountById = useMemo(() => new Map((accounts ?? []).map((a) => [a.id, a])), [accounts])
  const accountIds = useMemo(() => accounts?.map((a) => a.id) ?? [], [accounts])
  const { data: signalHistories, loading: signalHistoriesLoading } = useSignalHistories(accountIds)
  const isLoading = !alerts || !accounts || signalHistoriesLoading

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

  const shown = useMemo(() => {
    if (!alerts) return []
    const filtered = alerts.filter((a) => {
      if (filter !== "All" && STATUS_LABEL[a.status] !== filter) return false
      // Only exclude on real evidence (a loaded, short history), never just because it hasn't fetched yet.
      const history = signalHistories[a.account_id]
      if (history && !computeDataCoverage(history).isSufficient) return false
      return true
    })
    // Risk score is the priority signal now — highest risk first.
    return [...filtered].sort(
      (a, b) => (accountById.get(b.account_id)?.composite_score ?? -1) - (accountById.get(a.account_id)?.composite_score ?? -1),
    )
  }, [alerts, filter, accountById, signalHistories])

  const openCount = alerts?.filter((a) => a.status === "open").length ?? 0

  return (
    <div>
      <header className="rule px-10 pb-6 pt-8">
        <h1 className="text-[32px] tracking-[-0.03em]">Alerts</h1>
        <p className="mt-1.5 max-w-[66ch] text-[13.5px] text-neutral-700">
          Every account currently over the risk threshold, sorted from the highest risk score.
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
        {isLoading && <Loading rows={4} />}
        {!isLoading && alerts && shown.length === 0 && (
          <EmptyState title="Queue clear" body="Nothing in this filter needs your attention right now." />
        )}
        {!isLoading && shown.map((alert, i) => {
          const history = signalHistories[alert.account_id] ?? []
          return (
            <AlertCard
              key={alert.id}
              alert={alert}
              account={accountById.get(alert.account_id)}
              latestSignals={history[history.length - 1]}
              style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
              updating={updatingId === alert.id}
              justUpdated={justUpdatedId === alert.id}
              onUpdateStatus={updateStatus}
            />
          )
        })}
      </div>
    </div>
  )
}
