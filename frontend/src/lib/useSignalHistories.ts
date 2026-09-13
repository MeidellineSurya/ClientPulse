import { api } from "@/lib/api"
import { useBatchedByIds } from "@/lib/useBatchedByIds"
import type { SignalSnapshot } from "@/types/api"

// One agency-scoped request replaces the previous request-per-account queue.
export function useSignalHistories(ids: string[]) {
  return useBatchedByIds<SignalSnapshot[]>(ids, api.listSignalHistories)
}
