import { useEffect, useRef, useState } from "react"

import { api } from "@/lib/api"
import type { HealthScorePoint } from "@/types/api"

// Fetches GET /accounts/:id/health-history for a set of accounts, once each,
// and keeps the results keyed by account id. Used to draw per-row trend
// sparklines without re-fetching on every re-render (sort/filter changes
// produce a new `ids` array, but only ids not already fetched go out again).
export function useHealthHistories(ids: string[]): Record<string, HealthScorePoint[]> {
  const [histories, setHistories] = useState<Record<string, HealthScorePoint[]>>({})
  const fetched = useRef<Set<string>>(new Set())

  useEffect(() => {
    const pending = ids.filter((id) => !fetched.current.has(id))
    if (pending.length === 0) return
    pending.forEach((id) => fetched.current.add(id))

    pending.forEach((id) => {
      api
        .getAccountHealthHistory(id)
        .then((points) => setHistories((prev) => ({ ...prev, [id]: points })))
        .catch(() => {
          // Non-fatal: that row's sparkline just falls back to the trend arrow.
        })
    })
  }, [ids])

  return histories
}
