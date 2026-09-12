import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api, ApiError } from "@/lib/api"
import { formatDate, formatSignalName, severityStyles } from "@/lib/format"
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

export function Alerts() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [updatingId, setUpdatingId] = useState<string | null>(null)

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

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
        <p className="text-sm text-muted-foreground">Every flagged account, newest first.</p>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-3">
        {alerts?.map((alert) => (
          <Card key={alert.id}>
            <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Link to={`/accounts/${alert.account_id}`} className="hover:underline">
                    {alert.account_name ?? alert.account_id}
                  </Link>
                  <Badge variant="secondary" className={severityStyles[alert.severity]}>
                    {alert.severity}
                  </Badge>
                  <Badge variant="outline">{STATUS_LABEL[alert.status]}</Badge>
                </CardTitle>
                <p className="mt-1 text-xs text-muted-foreground">
                  Triggered {formatDate(alert.triggered_at)} · {alert.signals_fired.map(formatSignalName).join(", ")}
                </p>
              </div>
              {alert.status !== "resolved" && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={updatingId === alert.id}
                  onClick={() => advanceStatus(alert)}
                >
                  Mark {STATUS_LABEL[STATUS_FLOW[alert.status]]}
                </Button>
              )}
            </CardHeader>
            {alert.ai_brief && (
              <CardContent className="text-sm">
                {alert.ai_brief}
                {alert.suggested_action && (
                  <p className="mt-1 font-medium">Suggested action: {alert.suggested_action}</p>
                )}
              </CardContent>
            )}
          </Card>
        ))}
        {alerts !== null && alerts.length === 0 && (
          <p className="py-8 text-center text-muted-foreground">No alerts — everything's healthy.</p>
        )}
      </div>
    </div>
  )
}
