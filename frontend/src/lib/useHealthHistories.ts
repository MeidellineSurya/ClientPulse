import { api } from "@/lib/api"
import { useCachedByIds } from "@/lib/useCachedByIds"
import type { HealthScorePoint } from "@/types/api"

// Per-row trend sparkline data. Cached and throttled across every caller (see useCachedByIds).
export function useHealthHistories(ids: string[]): Record<string, HealthScorePoint[]> {
  return useCachedByIds("health-histories", ids, api.getAccountHealthHistory)
}
