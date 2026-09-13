import { api } from "@/lib/api"
import { useBatchedByIds } from "@/lib/useBatchedByIds"
import type { HealthScorePoint } from "@/types/api"

// One agency-scoped request supplies every row sparkline without an N+1 fan-out.
export function useHealthHistories(ids: string[]) {
  return useBatchedByIds<HealthScorePoint[]>(ids, api.listHealthHistories)
}
