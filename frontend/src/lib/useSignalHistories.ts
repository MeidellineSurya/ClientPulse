import { api } from "@/lib/api"
import { useCachedByIds } from "@/lib/useCachedByIds"
import type { SignalSnapshot } from "@/types/api"

// Raw-signal analog of useHealthHistories, for aggregating portfolio-wide trends. Cached and throttled across every caller.
export function useSignalHistories(ids: string[]): Record<string, SignalSnapshot[]> {
  return useCachedByIds("signal-histories", ids, api.getAccountSignals)
}
